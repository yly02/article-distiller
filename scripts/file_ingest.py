"""Convert local text, PDF and Word files into the Article input contract."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from dependency_bootstrap import ensure_python_dependencies, has_command
import json

from fetcher import Article, article_from_text, merge_page_assets


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}
HTML_EXTENSIONS = {".html", ".htm"}
JSON_EXTENSIONS = {".json"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
DOC_EXTENSIONS = {".doc"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | HTML_EXTENSIONS | JSON_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS | DOC_EXTENSIONS


def _fallback_title(path: Path) -> str:
    value = re.sub(r"[_-]+", " ", path.stem).strip()
    return value or "未命名文章"


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法按 UTF-8 或 GB18030 读取文件：{path}")


def _extract_pdf(path: Path) -> tuple[str, str, str]:
    ensure_python_dependencies(["pypdf"])
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(page for page in pages if page)
    metadata = reader.metadata or {}
    title = str(metadata.get("/Title") or "").strip()
    author = str(metadata.get("/Author") or "").strip()
    if not text:
        raise ValueError(
            f"PDF 没有可提取的文字：{path}。它可能是扫描件，请先 OCR，或提供可复制文字版。"
        )
    return text, title, author


def _iter_docx_blocks(document) -> Iterable[str]:
    """Yield paragraphs and tables in their original OOXML body order."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P

    parent = document.element.body
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            block = Paragraph(child, parent)
            value = block.text.strip()
            if value:
                yield value
        elif isinstance(child, CT_Tbl):
            table = Table(child, parent)
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                yield "\n".join(rows)


def _extract_docx(path: Path) -> tuple[str, str, str]:
    ensure_python_dependencies(["docx"])
    from docx import Document

    document = Document(str(path))
    text = "\n\n".join(_iter_docx_blocks(document)).strip()
    props = document.core_properties
    title = (props.title or "").strip()
    author = (props.author or "").strip()
    if not text:
        raise ValueError(f"Word 文档没有可提取的正文：{path}")
    return text, title, author


def _extract_legacy_doc(path: Path) -> tuple[str, str, str]:
    if not has_command("soffice"):
        raise RuntimeError(
            "读取 .doc 需要 LibreOffice（soffice），当前环境未找到。"
            "请安装 LibreOffice，或将文件另存为 .docx 后重试。"
        )
    with tempfile.TemporaryDirectory(prefix="article-distiller-doc-") as temp_dir:
        result = subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                temp_dir,
                str(path),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        converted = Path(temp_dir) / f"{path.stem}.docx"
        if result.returncode != 0 or not converted.exists():
            detail = (result.stdout or "").strip() or "LibreOffice 未生成转换文件"
            raise RuntimeError(f".doc 转换失败：{detail}")
        return _extract_docx(converted)


def _extract_html(path: Path) -> str:
    ensure_python_dependencies(["trafilatura", "lxml_html_clean"])
    import trafilatura

    raw = _read_text(path)
    return (trafilatura.extract(raw, include_comments=False, include_tables=True, favor_recall=True) or "").strip()



def _block_text(block: dict) -> str:
    kind = str(block.get("type") or "").strip().lower()
    text = str(block.get("text") or block.get("content") or "").strip()
    if not text:
        return ""
    if kind == "heading":
        try:
            level = int(block.get("level") or 2)
        except (TypeError, ValueError):
            level = 2
        level = min(max(level, 1), 6)
        return "#" * level + " " + text
    if kind == "list":
        items = block.get("items") if isinstance(block.get("items"), list) else []
        lines = [str(item).strip() for item in items if str(item).strip()]
        if not lines:
            lines = [part.strip() for part in text.split("\n") if part.strip()]
        rendered = []
        for part in lines:
            if part.startswith(("- ", "* ", "1.", "2.", "3.")):
                rendered.append(part)
            else:
                rendered.append("- " + part)
        return "\n".join(rendered)
    return text


def _article_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    article = payload.get("article")
    if isinstance(article, dict):
        return article
    if any(key in payload for key in ("body_blocks", "title", "source_url", "media_assets")):
        return payload
    return {}


def article_from_monitoring_json(
    payload: dict,
    *,
    url: str = "",
    title: str = "",
    author: str = "",
) -> Article:
    """Convert a monitoring.article.v2 export into Article plus registered media."""
    article_data = _article_payload(payload)
    if not article_data:
        raise ValueError("JSON 不是可识别的文章导出：需要 article 对象或 body_blocks")
    blocks = article_data.get("body_blocks") or article_data.get("blocks") or []
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("文章 JSON 缺少 body_blocks")
    lines = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        value = _block_text(block)
        if value:
            lines.append(value)
            lines.append("")
    text = "\n".join(lines).strip()
    if not text:
        raise ValueError("文章 JSON 的 body_blocks 没有可提取正文")
    source_url = (
        url.strip()
        or str(article_data.get("source_url") or article_data.get("url") or "").strip()
    )
    article = article_from_text(
        text,
        url=source_url,
        title=title.strip() or str(article_data.get("title") or "").strip(),
        author=author.strip() or str(article_data.get("author") or "").strip(),
    )
    images = []
    videos = []
    for index, item in enumerate(article_data.get("media_assets") or [], 1):
        if not isinstance(item, dict):
            continue
        src = str(item.get("url") or item.get("src") or "").strip()
        if not src:
            continue
        media_type = str(item.get("type") or "image").strip().lower()
        role = str(item.get("role") or item.get("asset_role") or "").strip().lower()
        if media_type == "image" and not role:
            caption = str(item.get("caption") or item.get("alt") or "").lower()
            role = "chart" if any(token in caption for token in ("chart", "graph", "plot", "图")) else "screenshot"
        record = {
            "id": str(item.get("id") or f"media-{index}").strip(),
            "src": src,
            "alt": str(item.get("alt") or item.get("caption") or "").strip(),
            "role": role or ("demo" if media_type == "video" else "screenshot"),
            "language": str(item.get("language") or "").strip(),
            "caption": str(item.get("caption") or item.get("alt") or "").strip(),
            "reader_note": str(item.get("reader_note") or "").strip(),
            "source_page": source_url,
            "embed": bool(item.get("embed")),
        }
        if media_type == "video":
            videos.append(record)
        else:
            images.append(record)
    merge_page_assets(article, {
        "media_discovery": {
            "status": "completed",
            "method": "user_json_export",
            "page_url": source_url,
            "registered_count": len(images) + len(videos),
            "missing_count": 0,
        },
        "images": images,
        "videos": videos,
    })
    discovery = article_data.get("media_discovery")
    if isinstance(discovery, dict):
        article.media_discovery = {
            **discovery,
            "status": "completed",
            "method": str(discovery.get("method") or discovery.get("source") or "user_json_export"),
        }
    else:
        article.media_discovery = {
            "status": "completed",
            "method": "user_json_export",
            "page_url": source_url,
        }
    return article


def article_from_file(
    file_path: str,
    *,
    url: str = "",
    title: str = "",
    author: str = "",
) -> Article:
    path = Path(os.path.abspath(os.path.expanduser(file_path)))
    if not path.is_file():
        raise FileNotFoundError(f"本地文件不存在：{path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"暂不支持 {suffix or '(无扩展名)'} 文件；支持：{supported}")

    extracted_title = ""
    extracted_author = ""
    if suffix in JSON_EXTENSIONS:
        try:
            payload = json.loads(_read_text(path))
        except json.JSONDecodeError as exc:
            raise ValueError(f"本地 JSON 不是合法文件：{path}（{exc}）") from exc
        return article_from_monitoring_json(payload, url=url, title=title, author=author)
    if suffix in TEXT_EXTENSIONS:
        text = _read_text(path).strip()
    elif suffix in HTML_EXTENSIONS:
        text = _extract_html(path)
    elif suffix in PDF_EXTENSIONS:
        text, extracted_title, extracted_author = _extract_pdf(path)
    elif suffix in DOCX_EXTENSIONS:
        text, extracted_title, extracted_author = _extract_docx(path)
    else:
        text, extracted_title, extracted_author = _extract_legacy_doc(path)
    if not text:
        raise ValueError(f"文件正文为空：{path}")
    source_url = url.strip() or path.as_uri()
    return article_from_text(
        text,
        url=source_url,
        title=title.strip() or extracted_title or _fallback_title(path),
        author=author.strip() or extracted_author,
    )
