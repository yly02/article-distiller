"""转义、正文段落和语义色。"""
from __future__ import annotations

import html
import re
from typing import Any

from urllib.parse import urlsplit

from fetcher import Article


def _esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "")


def _render_text_with_term_markers(
    text: str,
    term_refs: list[dict],
    used_targets: set[str],
) -> str:
    """Escape prose and append markers to non-overlapping first term mentions."""
    matches = []
    for ref in term_refs:
        marker_id = str(ref.get("marker_id") or "")
        term = str(ref.get("term") or "")
        if not marker_id or not term or marker_id in used_targets:
            continue
        position = text.find(term)
        if position >= 0:
            marker_end = position + len(term)
            if marker_end < len(text) and text[marker_end] in "（(":
                closing = "）" if text[marker_end] == "（" else ")"
                close_at = text.find(closing, marker_end + 1)
                if close_at >= 0 and close_at - marker_end <= 40 and "\n" not in text[marker_end:close_at]:
                    marker_end = close_at + 1
            matches.append((position, -len(term), term, marker_end, ref))
    matches.sort()

    accepted = []
    cursor = 0
    for position, _negative_length, term, marker_end, ref in matches:
        if position < cursor:
            continue
        accepted.append((position, term, marker_end, ref))
        cursor = marker_end

    if not accepted:
        return _esc(text)
    parts = []
    cursor = 0
    for position, term, marker_end, ref in accepted:
        marker_id = str(ref["marker_id"])
        popover_id = f"{marker_id}-popover"
        definition = str(ref.get("definition") or "")
        analogy = str(ref.get("analogy") or "")
        plain = (
            '<span class="term-popover-plain">'
            '<span class="term-popover-label">通俗理解</span>'
            f'{_esc(analogy)}</span>'
        ) if analogy else ""
        parts.append(_esc(text[cursor:marker_end]))
        parts.append(
            f'<sup class="term-marker-wrap" id="{_esc(marker_id)}">'
            '<button class="term-marker" type="button" data-term-popover-toggle '
            f'aria-label="查看“{_esc(term)}”的名词解释" '
            f'aria-describedby="{_esc(popover_id)}" aria-expanded="false">i</button>'
            f'<span class="term-popover" id="{_esc(popover_id)}" role="tooltip">'
            f'<strong class="term-popover-term">{_esc(term)}</strong>'
            f'<span class="term-popover-definition">{_esc(definition)}</span>'
            f'{plain}</span></sup>'
        )
        used_targets.add(marker_id)
        cursor = marker_end
    parts.append(_esc(text[cursor:]))
    return "".join(parts)


def _render_prose_paragraphs(value: Any, term_refs: list[dict] | None = None) -> str:
    """Render paragraphs and mark each glossary term at its first body mention."""
    text = str(value or "").strip()
    if not text:
        return ""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    rendered = []
    used_targets: set[str] = set()
    for paragraph in paragraphs:
        if paragraph.startswith("<blockquote ") or paragraph.startswith("<aside "):
            rendered.append(paragraph)
            continue
        normalized = re.sub(r"\s*\n\s*", " ", paragraph)
        prose = _render_text_with_term_markers(normalized, term_refs or [], used_targets)
        rendered.append(f"<p>{prose}</p>")
    return "".join(rendered)


_VERDICT_CLASS = {
    "确认": "v-ok",
    "交叉验证": "v-ok",
    "原文声称": "v-warn",
    "存疑": "v-warn",
    "夸大": "v-bad",
    "无法核实": "v-warn",
}


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value if str(item).strip())
    return str(value or "").strip()


def _visual_tone(value: Any) -> str:
    """Return a whitelisted semantic color role for public visual classes."""
    tone = str(value or "").strip().lower()
    return tone if tone in {"primary", "baseline", "warning", "danger"} else ""

