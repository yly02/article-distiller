"""研究、写作、审校流水线。"""
from __future__ import annotations

import copy
import json
import hashlib
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from fetcher import Article
from editorial_quality import assert_publishable, audit_distilled
from evidence import normalize_distilled, url_key
from language_quality import apply_safe_language_fixes

from .llm import (
    _call_json,
    _is_response_format_error,
    _is_retryable_llm_error,
    _is_streaming_error,
    _probe_llm_endpoint,
    _retry_wait_seconds,
    _serialize_draft,
    _serialize_research_ledger,
)
from .prompts import (
    FULL_SYSTEM_PROMPT,
    QUALITY_REPAIR_PATCH_PROMPT,
    RESEARCH_PROMPT,
    _editorial_patch_review_prompt_for_modes,
    _editorial_review_prompt_for_modes,
    _system_prompt_for_modes,
)

def _apply_article_patch(draft: dict, patch: dict) -> dict:
    """Apply a constrained top-level/section patch without losing untouched data."""
    if not isinstance(draft, dict) or not isinstance(patch, dict):
        raise ValueError("编辑审校阶段的 article_patch 不是对象")
    set_fields = patch.get("set_fields") or {}
    section_updates = patch.get("section_updates") or []
    if not isinstance(set_fields, dict) or not isinstance(section_updates, list):
        raise ValueError("article_patch.set_fields 或 section_updates 类型无效")
    forbidden = {"research_ledger", "editorial_quality"}
    unknown_fields = sorted(set(set_fields) - set(draft))
    forbidden_fields = sorted(set(set_fields) & forbidden)
    if unknown_fields or forbidden_fields:
        details = unknown_fields + forbidden_fields
        raise ValueError(f"article_patch 包含不允许的顶层字段：{details}")

    result = copy.deepcopy(draft)
    for key, value in set_fields.items():
        result[key] = copy.deepcopy(value)

    if "sections" in set_fields and section_updates:
        raise ValueError("替换完整 sections 时不能同时提交 section_updates")
    if not section_updates:
        return result

    sections = result.get("sections")
    if not isinstance(sections, list):
        raise ValueError("草稿缺少可更新的 sections")
    by_id = {
        str(item.get("id") or ""): item
        for item in sections
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    seen_ids: set[str] = set()
    for update in section_updates:
        if not isinstance(update, dict):
            raise ValueError("section_updates 中存在非对象条目")
        section_id = str(update.get("id") or "")
        if not section_id or section_id not in by_id:
            raise ValueError(f"section_updates 引用了不存在的 section id：{section_id or '(空)'}")
        if section_id in seen_ids:
            raise ValueError(f"section_updates 重复修改 section id：{section_id}")
        fields = update.get("set") or {}
        if not fields:
            # Some model responses flatten the requested `set` object and place
            # section fields beside `id`. Normalize that unambiguous legacy form
            # before applying the same allow-list validation below.
            fields = {key: value for key, value in update.items() if key != "id"}
        if not isinstance(fields, dict) or not fields:
            raise ValueError(f"section_updates[{section_id}] 缺少非空 set")
        unknown_section_fields = sorted(set(fields) - set(by_id[section_id]))
        if unknown_section_fields:
            raise ValueError(
                f"section_updates[{section_id}] 包含未知字段：{unknown_section_fields}"
            )
        for key, value in fields.items():
            by_id[section_id][key] = copy.deepcopy(value)
        seen_ids.add(section_id)
    return result


def _merge_repair_candidate(base: dict, repaired: dict, article: Article) -> dict:
    """合并定向修复稿，避免修复模型丢失已登记的证据和媒体决策。

    质量修复只应改阻断项。模型返回完整 JSON 时，字段遗漏、空列表或略写来源
    不应把已经通过前一阶段的媒体对账、数字来源和证据记录一起删除。
    """
    if not isinstance(base, dict) or not isinstance(repaired, dict):
        return copy.deepcopy(repaired)
    result = copy.deepcopy(base)
    known_urls = {url_key(str(getattr(article, "url", "") or ""))}
    for source in getattr(article, "source_links", []) or []:
        if isinstance(source, dict):
            key = url_key(str(source.get("url") or ""))
            if key:
                known_urls.add(key)
    for asset in getattr(article, "media_assets", []) or []:
        if isinstance(asset, dict):
            for value in (asset.get("url"), asset.get("source_url")):
                key = url_key(str(value or ""))
                if key:
                    known_urls.add(key)

    keyed_lists = {
        "source_media": "media_id",
        "media_omissions": "media_id",
        "evidence_gallery": "media_id",
        "number_stories": "id",
    }
    for key, value in repaired.items():
        if key in {"research_ledger", "editorial_quality"}:
            continue
        if key not in keyed_lists or not isinstance(value, list):
            result[key] = copy.deepcopy(value)
            continue
        previous = result.get(key)
        if not isinstance(previous, list):
            result[key] = copy.deepcopy(value)
            continue
        if not value and previous:
            continue
        id_field = keyed_lists[key]
        merged = {
            str(item.get(id_field) or ""): copy.deepcopy(item)
            for item in previous
            if isinstance(item, dict) and str(item.get(id_field) or "")
        }
        order = list(merged)
        for item in value:
            if not isinstance(item, dict):
                continue
            item_copy = copy.deepcopy(item)
            item_id = str(item_copy.get(id_field) or "")
            if key == "number_stories" and item_id:
                old = merged.get(item_id) or {}
                new_url = url_key(str(item_copy.get("source_url") or ""))
                old_url = url_key(str(old.get("source_url") or ""))
                if old_url in known_urls and new_url not in known_urls:
                    item_copy["source_url"] = old.get("source_url")
                if old.get("source_asset_ids") and not item_copy.get("source_asset_ids"):
                    item_copy["source_asset_ids"] = copy.deepcopy(old["source_asset_ids"])
            if item_id and item_id not in merged:
                order.append(item_id)
            if item_id:
                merged[item_id] = item_copy
        result[key] = [merged[item_id] for item_id in order]
    return result


def _review_output_mode() -> str:
    explicit = os.getenv("DISTILL_REVIEW_OUTPUT_MODE", "").strip().lower()
    if explicit in {"patch", "full"}:
        return explicit
    return "patch"


def _env_int(name: str, fallback: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(fallback))))
    except (TypeError, ValueError):
        return fallback


def _compact_source_registry(article: Article, evidence_articles: list[Article]) -> list[dict]:
    sources = [{
        "url": article.url,
        "title": article.title,
        "source_type": "original",
    }]
    sources.extend({
        "url": item.url,
        "title": item.title,
        "source_type": str(getattr(item, "source_type", "supplemental") or "supplemental"),
    } for item in evidence_articles if item.url)
    return sources


def _build_draft_context(
    article: Article,
    evidence_articles: list[Article],
    research: dict | None,
    full_user_prompt: str,
) -> str:
    """Avoid resending raw attachments after research while preserving the original."""
    if not isinstance(research, dict):
        return full_user_prompt
    ledger_limit = 40000
    sources = _compact_source_registry(article, evidence_articles)
    context = (
        f"原文标题：{article.title or '(未提取到)'}\n"
        f"作者：{article.author or '(未知)'}\n"
        f"发布日期：{article.date or '(未知)'}\n"
        f"原文 URL：{article.url}\n"
        f"允许引用的已抓取来源：{json.dumps(sources, ensure_ascii=False)}\n\n"
    )
    source_links = [
        item for item in (getattr(article, "source_links", []) or [])
        if isinstance(item, dict) and (item.get("fetched") or item.get("url") == article.url)
    ][:16]
    media_assets = []
    for item in (getattr(article, "media_assets", []) or []):
        if not isinstance(item, dict):
            continue
        # 只把模型真正需要做取舍的媒体元数据送入写作阶段，避免把网络请求、
        # CSS 背景图等重复的长字段塞进提示词。
        media_assets.append({
            key: item.get(key)
            for key in ("id", "type", "url", "poster_url", "alt", "section_title", "asset_role")
            if item.get(key)
        })
        if len(media_assets) >= 16:
            break
    context += (
        f"可用来源链接：{json.dumps(source_links, ensure_ascii=False)}\n"
        f"可用来源媒体：{json.dumps(media_assets, ensure_ascii=False)}\n\n"
        f"--- 原始文章正文（共 {article.text_chars} 字）---\n{article.text}\n\n"
    )
    context += (
        "--- 研究员生成的证据账本 ---\n"
        + _serialize_research_ledger(research, max_chars=ledger_limit)
        + "\n\n写作只能使用原始文章、证据账本和上列 URL。unknowns 不得被写成确定结论；"
        "不得因为附件正文不再重复发送而省略高优先级主张、实验、案例或证据边界。"
    )
    return context


_PIPELINE_CACHE_VERSION = "article-distiller-stage-cache-v2"


def _stable_asset_url(value: str) -> str:
    """去掉签名 query，避免动态媒体每次加载造成阶段缓存失效。"""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.scheme and parts.netloc:
            return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))
    except ValueError:
        pass
    return raw.split("?", 1)[0].split("#", 1)[0]


def _stable_media_fingerprint(article: Article) -> list[dict]:
    """只用重要媒体的稳定身份参与缓存指纹，不让装饰素材和签名 URL 触发重跑。"""
    important_roles = {"chart", "demo", "hero", "screenshot"}
    seen: set[tuple[str, str]] = set()
    items = []
    for item in (getattr(article, "media_assets", []) or []):
        if not isinstance(item, dict) or not item.get("url"):
            continue
        media_type = str(item.get("type") or "").lower()
        role = str(item.get("asset_role") or "").lower()
        if role not in important_roles and media_type not in {"video", "audio"}:
            continue
        stable_url = _stable_asset_url(str(item.get("url") or ""))
        key = (media_type, stable_url)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "type": media_type,
            "url": stable_url,
            "poster_url": _stable_asset_url(str(item.get("poster_url") or "")),
            "asset_role": role,
            "source_url": _stable_asset_url(str(item.get("source_url") or "")),
        })
    return sorted(items, key=lambda item: (item["type"], item["url"], item["asset_role"]))


def _hash_payload(value) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _article_fingerprint_data(article: Article, include_content: bool = True) -> dict:
    repository_files = [
        {
            "path": item.get("path"),
            "url": item.get("url"),
            **({"content_hash": _hash_payload(str(item.get("content") or ""))} if include_content else {}),
        }
        for item in (getattr(article, "repository_files", []) or [])
        if isinstance(item, dict)
    ]
    data = {
        "url": article.url,
        "title": article.title,
        "author": article.author,
        "date": article.date,
        "source_type": getattr(article, "source_type", "original"),
        "repository_files": sorted(repository_files, key=lambda item: (str(item.get("path")), str(item.get("url")))),
        "repository_read": dict(getattr(article, "repository_read", None) or {}),
    }
    if include_content:
        data["content_hash"] = getattr(article, "content_hash", "") or _hash_payload(article.text)
        data["media_assets"] = _stable_media_fingerprint(article)
    return data


def _pipeline_fingerprint(
    article: Article,
    evidence_articles: list[Article],
    cfg: dict,
    required_modes: tuple[str, ...],
    writing_prompt: str,
    _review_prompt: str,
    two_stage: bool,
    editorial_review: bool,
) -> str:
    return _hash_payload({
        "cache_version": _PIPELINE_CACHE_VERSION,
        "article": _article_fingerprint_data(article, include_content=True),
        # Evidence pages and GitHub landing pages often contain volatile counters or timestamps.
        # The output-specific cache expires after one day, so URL identity is safer for retries.
        "evidence": [_article_fingerprint_data(item, include_content=False) for item in evidence_articles],
        "model": cfg.get("model"),
        "base_url": cfg.get("base_url"),
        "required_modes": required_modes,
        "two_stage": two_stage,
        "editorial_review": editorial_review,
        "research_prompt_hash": _hash_payload(RESEARCH_PROMPT),
        "writing_prompt_hash": _hash_payload(writing_prompt),
        # Review protocol changes do not alter research or writing inputs. The
        # review checkpoint hashes its own prompt separately so switching
        # between patch/full output can reuse the expensive upstream stages.
        "draft_context_mode": "original+research-ledger",
    })


def _load_stage_checkpoint(
    checkpoint_dir: str | None,
    stage: str,
    fingerprint: str,
    parent_hash: str = "",
) -> dict | None:
    if not checkpoint_dir:
        return None
    path = Path(checkpoint_dir) / f"{stage}.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        max_age = _env_int("DISTILL_STAGE_CACHE_MAX_AGE_SECONDS", 86400, 1)
        created_at = float(stored.get("created_at") or path.stat().st_mtime)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"[阶段缓存] {stage} 检查点不可读，将重新生成：{type(exc).__name__}")
        return None
    age = time.time() - created_at
    if age > max_age:
        print(f"[阶段缓存] {stage} 检查点已过期（{int(age)} 秒），将重新生成")
        return None
    if not isinstance(stored, dict) or not isinstance(stored.get("payload"), dict):
        print(f"[阶段缓存] {stage} 检查点结构无效，将重新生成")
        return None
    stored_fingerprint = str(stored.get("fingerprint") or "")
    if stored_fingerprint != fingerprint:
        print(
            f"[阶段缓存] {stage} 流水线指纹变化 "
            f"({stored_fingerprint[:8] or 'missing'} -> {fingerprint[:8]})，将重新生成"
        )
        return None
    if stored.get("parent_hash", "") != parent_hash:
        print(f"[阶段缓存] {stage} 上游结果变化，将重新生成")
        return None
    print(f"[阶段缓存] 复用{stage}阶段结果：{path}")
    return stored["payload"]


def _save_stage_checkpoint(
    checkpoint_dir: str | None,
    stage: str,
    fingerprint: str,
    payload: dict,
    parent_hash: str = "",
) -> None:
    if not checkpoint_dir:
        return
    directory = Path(checkpoint_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stage}.json"
    temporary = directory / f".{stage}.{os.getpid()}.tmp"
    stored = {
        "fingerprint": fingerprint,
        "parent_hash": parent_hash,
        "created_at": time.time(),
        "payload": payload,
    }
    temporary.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(f"[阶段缓存] 已保存{stage}阶段结果：{path}")


def _load_config(config_path: Optional[str]) -> dict:
    if not config_path or not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _load_ccswitch_config(db_path: Optional[str] = None) -> dict:
    """读取 ccswitch 当前 Codex 提供商；失败时安静回退。"""
    path = os.path.expanduser(db_path or "~/.cc-switch/cc-switch.db")
    if not os.path.exists(path):
        return {}
    connection = None
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        provider = connection.execute(
            "select id, settings_config from providers "
            "where app_type=? and is_current=1 limit 1",
            ("codex",),
        ).fetchone()
        if provider is None:
            return {}
        settings = json.loads(provider["settings_config"] or "{}")
        auth = settings.get("auth") if isinstance(settings.get("auth"), dict) else {}
        api_key = next(
            (
                str(auth[key])
                for key in ("api_key", "apiKey", "key", "token", "openai_api_key", "OPENAI_API_KEY")
                if auth.get(key)
            ),
            "",
        )
        config_text = settings.get("config") if isinstance(settings.get("config"), str) else ""
        endpoint = connection.execute(
            "select url from provider_endpoints "
            "where app_type=? and provider_id=? order by id asc limit 1",
            ("codex", provider["id"]),
        ).fetchone()
        base_match = re.search(
            r'(?m)^\s*(?:base_url|baseUrl|baseURL|api_base|endpoint|openai_base_url|OPENAI_BASE_URL)\s*=\s*["\']([^"\']+)["\']',
            config_text,
        )
        base_url = base_match.group(1) if base_match else str(endpoint["url"] if endpoint else "")
        model_match = re.search(r'(?m)^\s*model\s*=\s*["\']([^"\']+)["\']', config_text)
        model = str(settings.get("model") or (model_match.group(1) if model_match else ""))
        if base_url and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        if not api_key or not base_url:
            return {}
        return {"api_key": api_key, "base_url": base_url, "model": model or "deepseek-chat"}
    except (sqlite3.Error, json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}
    finally:
        if connection is not None:
            connection.close()


def resolve_llm_settings(config: dict) -> dict:
    """合并优先级：环境变量 > config > ccswitch > 默认。"""
    explicit = {
        "base_url": os.getenv("DISTILL_LLM_BASE_URL")
        or config.get("base_url")
        or "https://api.deepseek.com",
        "api_key": os.getenv("DISTILL_LLM_KEY") or config.get("api_key") or "",
        "model": os.getenv("DISTILL_LLM_MODEL") or config.get("model") or "deepseek-chat",
    }
    if explicit["api_key"]:
        return explicit
    return _load_ccswitch_config() or explicit


def _repository_files_block(article: Article, max_chars: int = 12000) -> str:
    files = [
        item for item in (getattr(article, "repository_files", []) or [])
        if isinstance(item, dict) and item.get("path") and item.get("content")
    ]
    if not files:
        status = getattr(article, "repository_read", None) or {}
        if status.get("status") == "failed":
            return "\n[仓库深读未完成]\n" + str(status.get("reason") or "未能读取关键文件") + "\n"
        return ""
    parts = []
    used = 0
    for item in files:
        remaining = max_chars - used
        if remaining <= 0:
            break
        content = str(item.get("content") or "")[:remaining]
        used += len(content)
        parts.append(
            f"[仓库关键文件：{item.get('path')}]\n"
            f"URL：{item.get('url')}\n{content}"
        )
    return "\n\n" + "\n\n".join(parts) if parts else ""


def distill(
    article: Article,
    config_path: Optional[str] = None,
    evidence_articles: Optional[list[Article]] = None,
    two_stage: bool = True,
    editorial_review: bool = True,
    required_modes: tuple[str, ...] = ("full",),
    checkpoint_dir: str | None = None,
) -> dict:
    """把 Article 喂给 LLM，返回通过质量门禁的解读 dict。"""
    cfg = resolve_llm_settings(_load_config(config_path))
    if not cfg["api_key"]:
        raise RuntimeError(
            "没找到 LLM API key。请配置 ccswitch 当前 Codex 提供商、设置环境变量 "
            "DISTILL_LLM_KEY，或在 config.json 里填 api_key。\n"
            "国内可填 DeepSeek / 智谱 / 通义 / Kimi 的 key（都兼容 OpenAI 格式），并设 base_url。"
        )

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("缺少 openai 库，请先 pip install openai") from e

    evidence_articles = evidence_articles or []
    if set(required_modes) != {"full"}:
        raise ValueError("article-distiller 只支持 full 深度文章")
    evidence_limit = 5
    evidence_char_limit = 12000
    repository_char_limit = 12000
    evidence_block = ""
    if evidence_articles:
        chunks = []
        for i, ev in enumerate(evidence_articles[:evidence_limit], 1):
            role = str(getattr(ev, "source_type", "supplemental") or "supplemental")
            label = {"official": "官方附件", "independent": "独立来源", "supplemental": "补充材料"}.get(role, "补充材料")
            chunks.append(
                f"[{label} {i} · role={role}]\n"
                f"标题：{ev.title or '(未提取到)'}\n"
                f"作者：{ev.author or '(未知)'}\n"
                f"URL：{ev.url}\n"
                f"正文：\n{ev.text[:evidence_char_limit]}"
                f"{_repository_files_block(ev, max_chars=repository_char_limit)}"
            )
        evidence_block = (
            "\n\n--- 已抓取的补充来源 ---\n"
            "official 只能佐证发布方口径，supplemental 只能补背景；只有 independent 可计为独立交叉核验。未抓取链接不能计入。\n\n"
            + "\n\n".join(chunks)
        )

    source_links = getattr(article, "source_links", []) or []
    media_assets = getattr(article, "media_assets", []) or []
    user_prompt = (
        f"原文标题：{article.title or '(未提取到)'}\n"
        f"作者：{article.author or '(未知)'}\n"
        f"发布日期：{article.date or '(未知)'}\n"
        f"来源 URL：{article.url}\n"
        f"抓取时间：{getattr(article, 'retrieved_at', '') or '(未知)'}\n"
        f"原文内容哈希：{getattr(article, 'content_hash', '') or '(未知)'}\n"
        f"可用来源链接（不得编造新链接）：{json.dumps(source_links, ensure_ascii=False)}\n"
        f"可用来源媒体（来自原文或已抓取附件；source_media 只能从这里选择）：{json.dumps(media_assets, ensure_ascii=False)}\n"
        f"正文（共 {article.text_chars} 字）：\n\n{article.text}"
        f"{evidence_block}"
    )

    writing_system_prompt = _system_prompt_for_modes(required_modes)
    full_review_system_prompt = _editorial_review_prompt_for_modes(required_modes)
    review_output_mode = _review_output_mode()
    review_system_prompt = (
        _editorial_patch_review_prompt_for_modes(required_modes)
        if review_output_mode == "patch"
        else full_review_system_prompt
    )
    fingerprint = _pipeline_fingerprint(
        article,
        evidence_articles[:evidence_limit],
        cfg,
        required_modes,
        writing_system_prompt,
        review_system_prompt,
        two_stage,
        editorial_review,
    )

    cfg = dict(cfg)
    timeout_default = _env_int("DISTILL_LLM_TIMEOUT_SECONDS", 240, 30)
    retry_default = _env_int("DISTILL_LLM_MAX_RETRIES", 1, 0)
    retry_delay_default = _env_int("DISTILL_LLM_RETRY_DELAY_SECONDS", 4, 0)
    retry_wait_default = _env_int("DISTILL_LLM_RETRY_MAX_WAIT_SECONDS", 15, 0)
    stream_default = os.getenv("DISTILL_LLM_STREAM", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }
    cfg["_manual_max_retries"] = retry_default
    cfg["_retry_delay_seconds"] = retry_delay_default
    cfg["_retry_max_wait_seconds"] = retry_wait_default
    cfg["_stream"] = stream_default
    stage_timings: dict[str, float] = {}

    def call_stage(system_prompt: str, user_prompt: str, temperature: float, stage: str) -> dict:
        started = time.monotonic()
        try:
            return _call_json(client, cfg, system_prompt, user_prompt, temperature, stage=stage)
        finally:
            stage_timings[stage] = round(time.monotonic() - started, 3)

    client_kwargs = {
        "base_url": cfg["base_url"],
        "api_key": cfg["api_key"],
        "timeout": timeout_default,
        "max_retries": 0,
    }
    client = OpenAI(**client_kwargs)
    _probe_llm_endpoint(client, cfg)

    research = _load_stage_checkpoint(checkpoint_dir, "research", fingerprint) if two_stage else None
    if two_stage:
        if research is None:
            try:
                research = call_stage(
                    RESEARCH_PROMPT,
                    user_prompt,
                    temperature=0.1,
                    stage="研究阶段",
                )
                _save_stage_checkpoint(checkpoint_dir, "research", fingerprint, research)
            except ValueError as exc:
                print(f"[研究阶段警告] {exc}；已回退为单阶段写作。", file=sys.stderr)
            except Exception:  # noqa: BLE001
                raise
        if research is not None:
            editorial_prompt = _build_draft_context(
                article,
                evidence_articles[:evidence_limit],
                research,
                user_prompt,
            )
        else:
            editorial_prompt = user_prompt
    else:
        editorial_prompt = user_prompt

    research_hash = _hash_payload(research or {})
    draft = _load_stage_checkpoint(
        checkpoint_dir, "writing", fingerprint, parent_hash=research_hash
    )
    if draft is None:
        draft = call_stage(
            writing_system_prompt,
            editorial_prompt,
            temperature=0.35,
            stage="写作阶段",
        )
        _save_stage_checkpoint(
            checkpoint_dir, "writing", fingerprint, draft, parent_hash=research_hash
        )
    result = draft
    review_meta: dict = {"status": "skipped", "selected_version": "draft"}
    selected_language_fixes: list[dict] = []
    if editorial_review:
        try:
            ledger_limit = 40000
            review_context = (
                "--- 原文标题 ---\n"
                + (article.title or "(未提取到)")
                + "\n\n--- 研究证据账本 ---\n"
                + _serialize_research_ledger(research or {}, max_chars=ledger_limit)
                + "\n\n--- 待审校完整草稿 ---\n"
                + _serialize_draft(draft)
            )
            if review_output_mode == "patch":
                review_prompt = (
                    review_context
                    + "\n\n请完整审校草稿，修复你发现的事实覆盖、结构、表达、语病、媒体和视觉组织问题，"
                    "返回 quality_report 和 article_patch。"
                    "只回传实际修改字段，不要回传未修改内容。"
                )
            else:
                review_prompt = (
                    review_context
                    + "\n\n请完整审校草稿，修复你发现的事实覆盖、结构、表达、语病、媒体和视觉组织问题，"
                    "并返回完整 revised_article，"
                    "不要只返回修改建议或局部字段。"
                )
            review_parent_hash = _hash_payload({
                "research": research or {},
                "draft": draft,
                "review_prompt_hash": _hash_payload(review_system_prompt),
            })
            reviewed = _load_stage_checkpoint(
                checkpoint_dir, "review", fingerprint, parent_hash=review_parent_hash
            )
            if reviewed is None:
                reviewed = call_stage(
                    review_system_prompt,
                    review_prompt,
                    temperature=0.15,
                    stage="编辑审校阶段",
                )
                _save_stage_checkpoint(
                    checkpoint_dir,
                    "review",
                    fingerprint,
                    reviewed,
                    parent_hash=review_parent_hash,
                )

            def load_full_review_fallback(reason: str) -> dict:
                print(
                    f"[编辑审校阶段] 补丁无效（{reason}），自动回退完整修订",
                    flush=True,
                )
                fallback_parent_hash = _hash_payload({
                    "research": research or {},
                    "draft": draft,
                    "full_review_prompt_hash": _hash_payload(full_review_system_prompt),
                })
                fallback_prompt = (
                    review_context
                    + "\n\n上一次补丁响应无法安全合并。请重新完成主编审校，并返回完整 "
                    "revised_article；不要返回 article_patch、修改建议或局部字段。"
                )
                fallback = _load_stage_checkpoint(
                    checkpoint_dir,
                    "review_full_fallback",
                    fingerprint,
                    parent_hash=fallback_parent_hash,
                )
                if fallback is None:
                    fallback = call_stage(
                        full_review_system_prompt,
                        fallback_prompt,
                        temperature=0.15,
                        stage="编辑审校完整回退阶段",
                    )
                    _save_stage_checkpoint(
                        checkpoint_dir,
                        "review_full_fallback",
                        fingerprint,
                        fallback,
                        parent_hash=fallback_parent_hash,
                    )
                return fallback

            actual_review_output_mode = review_output_mode
            revised = reviewed.get("revised_article")
            if isinstance(revised, dict):
                actual_review_output_mode = "full"
            elif isinstance(reviewed.get("article_patch"), dict):
                try:
                    revised = _apply_article_patch(draft, reviewed["article_patch"])
                    actual_review_output_mode = "patch"
                except ValueError as patch_exc:
                    if review_output_mode != "patch":
                        raise
                    reviewed = load_full_review_fallback(str(patch_exc))
                    revised = reviewed.get("revised_article")
                    if not isinstance(revised, dict):
                        raise ValueError("编辑审校完整回退阶段缺少 revised_article 对象")
                    actual_review_output_mode = "full_fallback"
            elif review_output_mode == "patch":
                reviewed = load_full_review_fallback("缺少可合并的 article_patch 对象")
                revised = reviewed.get("revised_article")
                if not isinstance(revised, dict):
                    raise ValueError("编辑审校完整回退阶段缺少 revised_article 对象")
                actual_review_output_mode = "full_fallback"
            else:
                raise ValueError("编辑审校阶段缺少完整 revised_article 对象")
            fixed_revised, revised_language_fixes = apply_safe_language_fixes(revised)
            result = fixed_revised
            selected = "revised"
            selected_language_fixes = revised_language_fixes
            review_meta = {
                "status": "completed",
                "selected_version": selected,
                "output_mode": actual_review_output_mode,
                "model_report": reviewed.get("quality_report") if isinstance(reviewed.get("quality_report"), dict) else {},
                "selection_basis": "审校稿默认进入成稿后统一质检；不在写作过程中重复运行完整门禁",
            }
        except ValueError as exc:
            print(f"[编辑审校警告] {exc}；将检查草稿是否达到发布门槛。", file=sys.stderr)
            review_meta = {
                "status": "review_failed",
                "selected_version": "draft",
                "output_mode": review_output_mode,
                "error": str(exc),
            }

    result, final_language_fixes = apply_safe_language_fixes(result)
    language_fixes = selected_language_fixes + final_language_fixes
    # 统一门禁必须在来源、媒体和数字字段完成确定性规范化后运行；否则
    # 原始 LLM JSON 中尚未补齐的 registered 标记会被误判为未登记素材。
    result = normalize_distilled(dict(result), article)
    final_audit = audit_distilled(result, research, required_modes, strict_editorial=True)

    if editorial_review and not final_audit.get("publishable"):
        repair_parent_hash = _hash_payload({
            "research": research or {},
            "result": result,
            "blockers": final_audit.get("blockers") or [],
            "repair_prompt_hash": _hash_payload(QUALITY_REPAIR_PATCH_PROMPT),
        })
        repair_prompt = (
            "--- 原文标题 ---\n"
            + (article.title or "(未提取到)")
            + "\n\n--- 必须消除的严格发布阻断项 ---\n"
            + json.dumps({
                "blockers": final_audit.get("blockers") or [],
                "warnings": final_audit.get("warnings") or [],
                "metrics": {
                    key: value
                    for key, value in (final_audit.get("metrics") or {}).items()
                    if key in {
                        "semantically_missing_high_claim_ids",
                        "unsupported_numbers",
                        "missing_high_metric_story_ids",
                        "incomplete_number_story_ids",
                        "incomplete_high_metric_story_claim_ids",
                        "meta_narration_section_indexes",
                        "meta_narration_public_paths",
                    }
                },
            }, ensure_ascii=False)
            + "\n\n--- 研究证据账本（仅保留修复所需口径） ---\n"
            + _serialize_research_ledger(research or {}, max_chars=12000)
            + "\n\n--- 当前完整文章 ---\n"
            + _serialize_draft(result, max_chars=60000)
            + "\n\n只修复上述阻断项，不删减已经通过的事实、实验、案例、来源和边界。"
            "请返回可确定合并的 article_patch，不要返回完整 revised_article。"
        )
        print(
            f"[质量修复阶段] 严格门禁仍有 {len(final_audit.get('blockers') or [])} 个阻断项，"
            "启动一次定向修复"
        )
        repaired_response = _load_stage_checkpoint(
            checkpoint_dir, "repair", fingerprint, parent_hash=repair_parent_hash
        )
        if repaired_response is None:
            repaired_response = call_stage(
                QUALITY_REPAIR_PATCH_PROMPT,
                repair_prompt,
                temperature=0.1,
                stage="质量修复阶段",
            )
            _save_stage_checkpoint(
                checkpoint_dir,
                "repair",
                fingerprint,
                repaired_response,
                parent_hash=repair_parent_hash,
            )
        repair_patch = repaired_response.get("article_patch")
        repaired = None
        if isinstance(repair_patch, dict):
            repaired = _apply_article_patch(result, repair_patch)
        elif isinstance(repaired_response.get("revised_article"), dict):
            # 兼容旧缓存/旧端点，但新请求协议默认只返回 patch。
            repaired = _merge_repair_candidate(result, repaired_response["revised_article"], article)
        if isinstance(repaired, dict):
            fixed_repaired, repair_language_fixes = apply_safe_language_fixes(repaired)
            result = normalize_distilled(fixed_repaired, article)
            language_fixes += repair_language_fixes
            review_meta = {
                **review_meta,
                "repair_status": "completed",
                "repair_selected_version": "revised",
                "repair_model_report": repaired_response.get("quality_report")
                if isinstance(repaired_response.get("quality_report"), dict)
                else {},
            }
            final_audit = audit_distilled(result, research, required_modes, strict_editorial=True)
        else:
            review_meta = {
                **review_meta,
                "repair_status": "invalid_response",
                "repair_error": "质量修复阶段缺少可合并的 article_patch 对象",
            }

    assert_publishable(final_audit, "编辑审校后的文章")
    result["editorial_quality"] = {
        **review_meta,
        "language_fixes": language_fixes,
        "language_fix_count": len(language_fixes),
        "stage_timings_seconds": stage_timings,
        "final_audit": final_audit,
    }
    if research is not None:
        result["research_ledger"] = research
    return result


def build_manual_prompt(
    article: Article,
    evidence_articles: Optional[list[Article]] = None,
    required_modes: tuple[str, ...] = ("full",),
) -> str:
    """没 key 时的降级：返回让用户自己拿去任意 LLM 跑的解读 prompt 文本。"""
    evidence_articles = evidence_articles or []
    if set(required_modes) != {"full"}:
        raise ValueError("article-distiller 只支持 full 深度文章")
    evidence_limit = 5
    evidence_char_limit = 12000
    repository_char_limit = 12000
    evidence_block = ""
    if evidence_articles:
        chunks = []
        for i, ev in enumerate(evidence_articles[:evidence_limit], 1):
            role = str(getattr(ev, "source_type", "supplemental") or "supplemental")
            label = {"official": "官方附件", "independent": "独立来源", "supplemental": "补充材料"}.get(role, "补充材料")
            chunks.append(
                f"[{label} {i} · role={role}] {ev.title}\nURL：{ev.url}\n"
                f"{ev.text[:evidence_char_limit]}"
                f"{_repository_files_block(ev, max_chars=repository_char_limit)}"
            )
        evidence_block = "\n\n--- 已抓取的补充来源 ---\n只有 independent 可计为独立交叉核验。\n" + "\n\n".join(chunks)
    return (
        "# 解读 Prompt（复制到任意 LLM 对话框使用）\n\n"
        "把下面这段原文按下列要求做二次解读，严格输出 JSON：\n\n"
        "--- 原文信息 ---\n"
        f"标题：{article.title or '(未提取到)'}\n"
        f"作者：{article.author or '(未知)'}\n"
        f"来源：{article.url or '(未知)'}\n\n"
        f"可用来源媒体：{json.dumps(getattr(article, 'media_assets', []) or [], ensure_ascii=False)}\n\n"
        "--- 原文正文 ---\n"
        f"{article.text}\n\n"
        f"{evidence_block}\n\n"
        "--- 解读要求与输出格式 ---\n"
        f"{_system_prompt_for_modes(required_modes)}\n"
    )
