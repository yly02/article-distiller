"""页眉、目录、来源区、类比和术语。"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from fetcher import Article

from .text import _esc, _render_prose_paragraphs, _render_text_with_term_markers

def _render_category_tags(tags: list) -> str:
    if not tags:
        return ""
    chips = "".join(f'<span class="category-tag">{_esc(t)}</span>' for t in tags)
    return f'<div class="category-tags">{chips}</div>'


def _source_outlet_name(article: Article) -> str:
    """Return a reader-facing source name, not the original headline."""
    host = (urlsplit(str(article.url or "")).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    known = {
        "epoch.ai": "Epoch AI",
        "openai.com": "OpenAI",
        "blog.google": "Google",
        "anthropic.com": "Anthropic",
        "nvidia.com": "Nvidia",
        "huawei.com": "Huawei",
        "arxiv.org": "arXiv",
        "github.com": "GitHub",
    }
    if host in known:
        return known[host]
    for suffix, name in known.items():
        if host.endswith("." + suffix):
            return name
    if host:
        label = host.split(".")[0].replace("-", " ").strip()
        return label.title() if label else "主材料"
    title = str(article.title or "主材料").strip()
    return title.rstrip("？?") or title


def _render_source_panel(
    article: Article,
    further_reading: list,
    source_note: str,
    fact_check: list,
) -> str:
    """Render only reader-facing provenance as a compact editorial footer.

    ``fact_check`` and ``source_notes`` are retained in the data model for
    internal audit and traceability, but must never be promoted into the
    public page.  ``source_note`` is supplied only from the reader-facing
    ``site_note``/bias fields by ``render_html``.
    """
    primary_title = _esc(_source_outlet_name(article))
    meta = []
    if article.author:
        meta.append(f'<span>{_esc(article.author)}</span>')
    if article.date:
        meta.append(f'<time>{_esc(article.date)}</time>')
    source_body = (
        f'<span class="source-title">{primary_title}</span>'
        f'<span class="source-meta">{"".join(meta)}</span>'
    )
    rows = [
        '<div class="source-row"><div class="source-label">来源</div>'
        f'<div class="source-content">{source_body}</div></div>'
    ]

    extras = []
    seen_titles = {str(article.title or "").strip()}
    for item in list(further_reading or []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        extras.append(f'<span>{_esc(title)}</span>')
    if extras:
        rows.append(
            '<div class="source-row"><div class="source-label">延伸</div>'
            f'<div class="source-content source-links">{"".join(extras[:5])}</div></div>'
        )
    if source_note:
        rows.append(
            '<div class="source-row"><div class="source-label">本站说明</div>'
            f'<div class="source-content"><p class="source-note">{_esc(source_note)}</p></div></div>'
        )
    return f'<footer class="source-panel">{"".join(rows)}</footer>'


def _render_bias_note(bias: str) -> str:
    if not bias:
        return ""
    return f'<div class="bias-note">{_esc(bias)}</div>'


def _render_rec_reason(reason: str) -> str:
    """推荐理由不单独上页；有价值的句子并进一分钟速览。"""
    return ""


def _section_dom_id(section: dict, index: int) -> str:
    """返回稳定且可安全用于 HTML/JS 的 ASCII 段落锚点。"""
    raw_id = str(section.get("id") or "").strip()
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_id).strip("-_")
    if safe_id and re.match(r"^[A-Za-z]", safe_id):
        return safe_id
    return f"sec-{index}"


def _section_display_title(section: dict) -> str:
    """Return the reader-facing title without an internal category label."""
    title = str(section.get("title") or "").strip()
    tag = str(section.get("tag") or "").strip()
    if not title or not tag:
        return title
    for prefix in (f"[{tag}]", f"【{tag}】"):
        if title.startswith(prefix):
            return title[len(prefix):].lstrip()
    return title


def _render_toc(sections: list) -> str:
    """Render a responsive off-flow table of contents."""
    if not sections:
        return ""
    items = []
    for i, s in enumerate(sections):
        title = _section_display_title(s)
        if not title:
            continue
        target_id = _section_dom_id(s, i)
        items.append(
            f'<li class="toc-item">'
            f'<span class="toc-num">{i+1}</span>'
            f'<a class="toc-link" data-section-target="{target_id}" href="#{target_id}" '
            f'onclick="var e=document.getElementById(\'{target_id}\');'
            f"if(e){{e.scrollIntoView({{behavior:'smooth'}})}}\""
            f'>{_esc(title)}</a></li>'
        )
    if not items:
        return ""
    return (
        '<details class="toc-card" data-reading-rail="toc">'
        '<summary class="toc-heading">\u76EE\u5F55</summary>'
        f'<ul class="toc-list">{"".join(items)}</ul>'
        '</details>'
    )


def _build_margin_rail(
    sections: list,
) -> tuple[str, dict[int, list[dict]], dict[int, list[dict]]]:
    """Build inline term popovers and a rail only for necessary source quotes."""
    items = []
    seen = set()
    term_count = 0
    quote_count = 0
    term_refs: dict[int, list[dict]] = {i: [] for i in range(len(sections))}
    citations: dict[int, list[dict]] = {i: [] for i in range(len(sections))}
    for index, section in enumerate(sections):
        for explainer in section.get("concept_explainers") or []:
            term = str(explainer.get("term") or "").strip()
            definition = str(explainer.get("definition") or "").strip()
            analogy = str(explainer.get("analogy") or "").strip()
            key = term.casefold()
            if not term or not definition or key in seen:
                continue
            seen.add(key)
            term_count += 1
            marker_id = f"term-marker-{term_count}"
            marker_section = next((
                section_index
                for section_index, candidate in enumerate(sections)
                if term in str(candidate.get("content") or "")
            ), None)
            if marker_section is not None:
                term_refs[marker_section].append({
                    "term": term,
                    "definition": definition,
                    "analogy": analogy,
                    "marker_id": marker_id,
                })

        archives = section.get("archive_original") or []
        if isinstance(archives, dict):
            archives = [archives]
        for archive in archives:
            if not isinstance(archive, dict):
                continue
            original = str(archive.get("original") or "").strip()
            translation = str(archive.get("translation") or "").strip()
            if not original and not translation:
                continue
            quote_count += 1
            note_id = f"margin-quote-{quote_count}"
            citations[index].append({"number": quote_count, "target_id": note_id})
            quote_parts = [
                f'<aside class="glossary-item margin-note margin-quote" id="{note_id}" tabindex="-1">',
                f'<span class="margin-note-kind">原文引文 {quote_count}</span>',
            ]
            if original:
                quote_parts.extend([
                    '<div class="margin-quote-label">英文原句</div>',
                    f'<div class="margin-quote-original" lang="en">{_esc(original)}</div>',
                ])
            if translation:
                quote_parts.extend([
                    '<div class="margin-quote-label">中文释义</div>',
                    f'<div class="margin-quote-translation">{_esc(translation)}</div>',
                ])
            quote_parts.append('</aside>')
            items.append("".join(quote_parts))
    if not items:
        return "", term_refs, citations
    rail_html = (
        '<details class="glossary-rail margin-rail" data-reading-rail="margin">'
        '<summary class="glossary-heading"><span>原文引文</span>'
        f'<span class="glossary-count">{quote_count} 条</span></summary>'
        f'<div class="glossary-list">{"".join(items)}</div></details>'
    )
    return rail_html, term_refs, citations


def _render_margin_citations(citations: list[dict]) -> str:
    """Keep a compact, clickable quotation reference in the body."""
    if not citations:
        return ""
    links = "".join(
        f'<a class="margin-cite" href="#{_esc(item["target_id"])}" '
        f'data-margin-note-target="{_esc(item["target_id"])}">[{item["number"]}]</a>'
        for item in citations
    )
    return (
        '<div class="margin-citations">'
        '<span class="margin-citations-label">相关引文</span>'
        f'{links}</div>'
    )


def _render_one_analogy(item: dict) -> str:
    concept = _esc(item.get("concept") or "")
    analogy = _esc(item.get("analogy") or "")
    if not analogy:
        return ""
    concept_html = f'<span class="art-analogy-term">{concept}</span>' if concept else ""
    return (
        '<blockquote class="art-annotation art-quote">'
        '<span class="art-annotation-label">类比</span>'
        f'<div class="art-analogy-copy">{concept_html}'
        f'<span class="art-analogy-text">{analogy}</span></div>'
        '</blockquote>'
    )


def _render_analogies_inline(analogies: list) -> str:
    """Render leftover analogies that could not be anchored to a sentence."""
    return "".join(_render_one_analogy(item) for item in analogies or [])


def _insert_analogies_into_content(content: str, analogies: list) -> tuple[str, list]:
    """Place each analogy after the sentence that first names its concept."""
    remaining = []
    text = content or ""
    for item in analogies or []:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept") or "").strip()
        card = _render_one_analogy(item)
        if not concept or not card or concept not in text:
            remaining.append(item)
            continue
        idx = text.find(concept)
        end = idx
        while end < len(text) and text[end] not in "。！？\n":
            end += 1
        if end < len(text) and text[end] in "。！？":
            end += 1
        text = text[:end] + "\n\n" + card + "\n\n" + text[end:].lstrip()
    return text, remaining


def _render_concepts_inline(explainers: list) -> str:
    """Render term, definition and plain-language explanation as distinct levels."""
    if not explainers:
        return ""
    parts = []
    for e in explainers:
        term = _esc(e.get("term") or "")
        definition = _esc(e.get("definition") or "")
        analogy = _esc(e.get("analogy") or "")
        line = (
            '<aside class="art-annotation art-note">'
            '<div class="art-concept-head">'
            '<span class="art-annotation-label">名词解释</span>'
            f'<span class="art-concept-term">{term}</span></div>'
            f'<div class="art-concept-definition">{definition}</div>'
        )
        if analogy:
            line += (
                '<div class="art-concept-plain">'
                '<span class="art-mini-label">通俗理解</span>'
                f'{analogy}</div>'
            )
        line += '</aside>'
        parts.append(line)
    return "".join(parts)
