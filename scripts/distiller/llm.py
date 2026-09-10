"""OpenAI 兼容接口调用。"""
from __future__ import annotations

import json
import sys
import time

def _is_response_format_error(exc: Exception) -> bool:
    """只对明确的 response_format 兼容性错误重试，避免吞掉鉴权/限流等错误。"""
    message = str(exc).lower()
    status_code = getattr(exc, "status_code", None)
    mentions_format = "response_format" in message or "json_object" in message
    unsupported = any(word in message for word in ("unsupported", "not support", "unknown", "invalid"))
    return mentions_format and unsupported and status_code in (None, 400, 404, 422)


def _serialize_research_ledger(research: dict, max_chars: int = 40000) -> str:
    """限制账本注入体积；保留结构，优先裁掉低优先级尾部主张。"""
    serialized = json.dumps(research, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return serialized

    compact = dict(research)
    claims = list(compact.get("claims") or [])[:50]
    compact["claims"] = claims
    compact["background"] = list(compact.get("background") or [])[:20]
    compact["unknowns"] = list(compact.get("unknowns") or [])[:20]
    compact["experiments"] = list(compact.get("experiments") or [])[:12]
    compact["cases"] = list(compact.get("cases") or [])[:12]
    compact["source_assessment"] = str(compact.get("source_assessment") or "")[:3000]
    compact["ledger_truncated"] = True
    while claims and len(json.dumps(compact, ensure_ascii=False)) > max_chars:
        claims.pop()
    serialized = json.dumps(compact, ensure_ascii=False)
    if len(serialized) > max_chars:
        compact = {
            "claims": [],
            "experiments": [],
            "cases": [],
            "background": [],
            "unknowns": ["证据账本因体积过大已省略；写作必须保守，不得补写材料外事实。"],
            "source_assessment": str(research.get("source_assessment") or "")[:1000],
            "ledger_truncated": True,
        }
        serialized = json.dumps(compact, ensure_ascii=False)
    return serialized


def _serialize_draft(draft: dict, max_chars: int = 60000) -> str:
    """限制审校阶段的草稿体积，并始终返回合法 JSON。"""
    serialized = json.dumps(draft, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return serialized
    compact = dict(draft)
    compact["draft_truncated_for_review"] = True
    for field, limit in (
        ("sections", 12), ("experiment_ledger", 12), ("case_stories", 12),
        ("number_stories", 20), ("evidence_gallery", 20),
        ("fact_check", 20), ("visuals", 8), ("source_media", 12),
        ("media_omissions", 20),
    ):
        if isinstance(compact.get(field), list):
            compact[field] = compact[field][:limit]
    serialized = json.dumps(compact, ensure_ascii=False)
    if len(serialized) > max_chars:
        compact = {
            "distilled_title": compact.get("distilled_title"),
            "one_liner": compact.get("one_liner"),
            "quick_scan": compact.get("quick_scan"),
            "sections": list(compact.get("sections") or [])[:8],
            "visuals": list(compact.get("visuals") or [])[:6],
            "source_media": list(compact.get("source_media") or [])[:8],
            "number_stories": list(compact.get("number_stories") or [])[:12],
            "draft_truncated_for_review": True,
        }
        serialized = json.dumps(compact, ensure_ascii=False)
        if len(serialized) > max_chars:
            serialized = json.dumps({
                "distilled_title": compact.get("distilled_title"),
                "sections": list(compact.get("sections") or [])[:4],
                "draft_truncated_for_review": True,
            }, ensure_ascii=False)
    return serialized


def _probe_llm_endpoint(client, cfg: dict) -> None:
    """Fail fast on empty, HTML, quota, or model-not-found responses before long stages."""
    if str(cfg.get("api_key") or "") == "test-key":
        return
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": "You return JSON only."},
                {"role": "user", "content": '{"ok": true}'},
            ],
            temperature=0,
            max_tokens=16,
        )
        content = ""
        try:
            content = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            content = str(response or "")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "LLM 接口预检失败，已停止长文生成。"
            f" 当前模型 {cfg.get('model')} / {cfg.get('base_url')}："
            f"{_llm_error_summary(exc)}。请核对 api_key、base_url 是否以 /v1 结尾、模型名是否在该端点可用。"
        ) from exc
    preview = str(content).strip()
    if not preview or preview.lstrip().startswith("<!") or "<html" in preview.lower():
        raise RuntimeError(
            "LLM 接口预检失败：返回空内容或 HTML 门户页，而不是 JSON。"
            f" 当前模型 {cfg.get('model')} / {cfg.get('base_url')}。"
        )


def _llm_error_summary(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status:
        return f"HTTP {status} {exc.__class__.__name__}"
    return exc.__class__.__name__


def _is_retryable_llm_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 429, 500, 502, 503, 504, 524}:
        return True
    name = exc.__class__.__name__.lower()
    return "timeout" in name or "connection" in name


def _retry_wait_seconds(exc: Exception, cfg: dict, attempt: int) -> float:
    base = float(cfg.get("_retry_delay_seconds", 8) or 0) * attempt
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        requested = float(retry_after) if retry_after is not None else 0.0
    except (TypeError, ValueError):
        requested = 0.0
    maximum = float(cfg.get("_retry_max_wait_seconds", 30) or 0)
    return max(0.0, min(max(base, requested), maximum))


def _is_streaming_error(exc: Exception) -> bool:
    message = str(exc).lower()
    status_code = getattr(exc, "status_code", None)
    return (
        status_code in (None, 400, 404, 422)
        and ("stream" in message or "streaming" in message)
        and any(word in message for word in ("unsupported", "not support", "unknown", "invalid"))
    )


def _create_completion(client, kwargs: dict, streaming: bool):
    request_kwargs = dict(kwargs)
    if streaming:
        request_kwargs["stream"] = True
    try:
        return client.chat.completions.create(
            response_format={"type": "json_object"}, **request_kwargs
        )
    except Exception as exc:  # noqa: BLE001
        if not _is_response_format_error(exc):
            raise
        return client.chat.completions.create(**request_kwargs)


def _completion_content(response, streaming: bool) -> str:
    choices = getattr(response, "choices", None)
    if choices is not None:
        try:
            return choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError) as exc:
            raise ValueError("模型返回结构异常，未找到 choices[0].message.content") from exc
    if not streaming:
        raise ValueError("模型返回结构异常，非流式响应缺少 choices")

    chunks: list[str] = []
    try:
        for chunk in response:
            try:
                choice = chunk.choices[0]
            except (AttributeError, IndexError, TypeError):
                continue
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if isinstance(content, str):
                chunks.append(content)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    return "".join(chunks)


def _call_json(
    client,
    cfg: dict,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    stage: str = "LLM 阶段",
) -> dict:
    kwargs = dict(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    manual_retries = cfg.get("_manual_max_retries")
    total_attempts = int(manual_retries) + 1 if manual_retries is not None else 1
    input_chars = len(system_prompt) + len(user_prompt)
    content = None
    streaming = bool(cfg.get("_stream", True))
    for attempt in range(1, total_attempts + 1):
        started = time.monotonic()
        suffix = f"/{total_attempts}" if total_attempts > 1 else ""
        transport = "流式" if streaming else "非流式"
        print(
            f"[{stage}] 模型调用 {attempt}{suffix} · 输入 {input_chars} 字 · {transport}",
            flush=True,
        )
        try:
            try:
                response = _create_completion(client, kwargs, streaming)
            except Exception as exc:  # noqa: BLE001
                if not streaming or not _is_streaming_error(exc):
                    raise
                print(f"[{stage}] 当前端点不支持流式返回，回退为非流式", flush=True)
                response = _create_completion(client, kwargs, False)
            content = _completion_content(response, streaming and not hasattr(response, "choices"))
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - started
            retryable = manual_retries is not None and _is_retryable_llm_error(exc)
            if not retryable or attempt >= total_attempts:
                print(
                    f"[{stage}] 调用失败 · {elapsed:.1f} 秒 · {_llm_error_summary(exc)}",
                    file=sys.stderr,
                    flush=True,
                )
                raise
            wait_seconds = _retry_wait_seconds(exc, cfg, attempt)
            print(
                f"[{stage}] 第 {attempt} 次失败 · {elapsed:.1f} 秒 · "
                f"{_llm_error_summary(exc)} · {wait_seconds:.0f} 秒后重试",
                file=sys.stderr,
                flush=True,
            )
            if wait_seconds:
                time.sleep(wait_seconds)
            continue
        elapsed = time.monotonic() - started
        print(f"[{stage}] 模型返回 · {elapsed:.1f} 秒", flush=True)
        break
    if content is None:
        raise RuntimeError(f"{stage}未获得模型响应")

    try:
        result = _safe_json_load(content)
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        preview = str(content).strip().replace("\n", " ")[:160]
        raise ValueError(f"{stage}未返回合法 JSON（开头：{preview!r}）") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{stage}返回的 JSON 顶层必须是对象")
    return result


def _safe_json_load(content: str) -> dict:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 兜底：剥掉可能的 ```json 包裹
        if content.startswith("```"):
            content = content.strip("`")
            if "{" in content and "}" in content:
                content = content[content.find("{") : content.rfind("}") + 1]
        return json.loads(content)


