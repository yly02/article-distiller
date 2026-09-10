"""实验、案例、来源媒体、数字叙事和试听卡。"""
from __future__ import annotations

from typing import Any

from .text import _display_value, _esc, _visual_tone

def _render_experiment(experiment: dict) -> str:
    if experiment.get("suppress_visual") is True or experiment.get("display_mode") == "audit_only":
        return ""
    title = experiment.get("title") or experiment.get("question") or ""
    experiment_id = experiment.get("id") or ""
    question = experiment.get("question") or ""
    fields = [
        ("实验设置", experiment.get("setup")),
        ("样本与轮次", experiment.get("sample")),
        ("模型", experiment.get("models")),
        ("判定指标", experiment.get("metric")),
        ("对照或基线", experiment.get("control")),
    ]
    result = experiment.get("result") or ""
    limitations = experiment.get("limitations") or ""
    claim_ids = [str(x) for x in (experiment.get("claim_ids") or []) if str(x).strip()]
    if not any((title, question, result)):
        return ""
    parts = [
        f'<details class="experiment-block" data-experiment-id="{_esc(experiment_id)}" '
        f'data-claim-ids="{_esc(",".join(claim_ids))}">',
        f'<summary><span class="experiment-title">{_esc(title)}</span></summary>',
        '<div class="experiment-body">',
    ]
    if question:
        parts.append(f'<div class="experiment-question">{_esc(question)}</div>')
    field_html = []
    for label, value in fields:
        display = _display_value(value)
        if display:
            field_html.append(
                '<div class="experiment-field">'
                f'<div class="experiment-label">{_esc(label)}</div>'
                f'<div class="experiment-value">{_esc(display)}</div>'
                '</div>'
            )
    if field_html:
        parts.append(f'<div class="experiment-grid">{"".join(field_html)}</div>')
    if result:
        parts.append(f'<div class="experiment-result"><strong>结果：</strong>{_esc(result)}</div>')
    if limitations:
        parts.append(f'<div class="experiment-limit"><strong>边界：</strong>{_esc(limitations)}</div>')
    parts.append('</div></details>')
    return "".join(parts)


def _render_case_story(story: dict) -> str:
    if story.get("suppress_visual") is True or story.get("display_mode") == "audit_only":
        return ""
    title = story.get("title") or ""
    setup = story.get("setup") or ""
    beats = [beat for beat in (story.get("beats") or []) if isinstance(beat, dict)]
    outcome = story.get("outcome") or ""
    boundary = story.get("boundary") or ""
    source_mode = str(story.get("source_mode") or "reconstruction").lower()
    claim_ids = [str(x) for x in (story.get("claim_ids") or []) if str(x).strip()]
    if not title or not beats:
        return ""
    parts = [
        f'<section class="case-story" data-case-id="{_esc(story.get("id") or "")}" '
        f'data-claim-ids="{_esc(",".join(claim_ids))}">',
        f'<div class="case-title">{_esc(title)}</div>',
    ]
    if setup:
        parts.append(f'<div class="case-setup">{_esc(setup)}</div>')
    parts.append('<div class="case-beats">')
    for beat in beats:
        label = beat.get("label") or "阶段"
        text = beat.get("text") or ""
        if not text:
            continue
        quote = beat.get("source_quote") or ""
        parts.append(
            '<div class="case-beat">'
            f'<div class="case-beat-label">{_esc(label)}</div>'
            f'<div class="case-beat-text">{_esc(text)}</div>'
        )
        if quote:
            parts.append(f'<blockquote class="case-source-quote">{_esc(quote)}</blockquote>')
        parts.append('</div>')
    parts.append('</div>')
    if outcome:
        parts.append(f'<div class="case-outcome">结果：{_esc(outcome)}</div>')
    if boundary:
        parts.append(f'<div class="case-boundary"><strong>不能据此证明：</strong>{_esc(boundary)}</div>')
    provenance = "含原文逐字引文" if source_mode == "quoted" else "基于证据重建事件顺序，非逐字对话"
    parts.append(f'<div class="case-provenance">{_esc(provenance)}')
    parts.append('</div></section>')
    return "".join(parts)

def _render_source_media(item: dict) -> str:
    """渲染一项已登记的来源媒体；未登记项永不进入发布页。"""
    if item.get("registered") is not True:
        return ""
    media_type = str(item.get("type") or "").strip().lower()
    url = str(item.get("url") or "").strip()
    if media_type not in {"image", "video"} or not url:
        return ""
    caption = str(item.get("caption") or "").strip()
    reader_note = str(item.get("reader_note") or "").strip()
    media_id = str(item.get("media_id") or "").strip()
    if media_type == "video" and item.get("embed") is True:
        media_html = (
            '<div class="source-media-embed">'
            f'<iframe src="{_esc(url)}" title="{_esc(caption or "原文视频")}" '
            'loading="lazy" allow="accelerometer; autoplay; encrypted-media; picture-in-picture" '
            'allowfullscreen></iframe></div>'
        )
    elif media_type == "video":
        poster = str(item.get("poster_url") or "").strip()
        poster_attr = f' poster="{_esc(poster)}"' if poster else ""
        media_html = (
            f'<video controls preload="metadata"{poster_attr}>'
            f'<source src="{_esc(url)}">'
            "当前浏览器无法播放该视频。"
            "</video>"
        )
    else:
        alt = caption or "原文图片"
        media_html = f'<img src="{_esc(url)}" alt="{_esc(alt)}" loading="lazy" decoding="async">'
    figcaption = f'<figcaption>{_esc(caption)}</figcaption>' if caption else ""
    note_label = "观看重点" if media_type == "video" else "读图提示"
    reader_html = (
        f'<div class="media-reader-note"><strong>{note_label}：</strong>'
        f'{_esc(reader_note)}</div>'
        if reader_note else ""
    )
    return (
        f'<figure class="source-media" data-media-id="{_esc(media_id)}">'
        f'{media_html}{figcaption}{reader_html}</figure>'
    )


def _render_ai_illustration(item: dict) -> str:
    """AI 图只承担解释功能，必须显式标注且不能伪装成来源媒体。"""
    if item.get("status") != "generated":
        return ""
    image_uri = str(item.get("image_data_uri") or item.get("image_path") or "").strip()
    if not image_uri:
        return ""
    title = str(item.get("title") or "AI 概念示意").strip()
    alt = str(item.get("alt") or title).strip()
    caption = str(item.get("caption") or "").strip()
    note = caption or f"{title}：根据正文制作的概念示意，用于辅助理解，不是原始证据。"
    return (
        f'<figure class="ai-illustration" data-illustration-id="{_esc(item.get("id") or "")}">'
        f'<img src="{_esc(image_uri)}" alt="{_esc(alt)}" loading="lazy" decoding="async">'
        f'<figcaption><span class="ai-label">AI 概念示意</span>{_esc(note)}</figcaption>'
        '</figure>'
    )


def _render_number_story(item: dict) -> str:
    if item.get("suppress_visual") is True or item.get("display_mode") == "audit_only":
        return ""
    title = str(item.get("title") or "这个数字意味着什么").strip()
    value = str(item.get("value") or "").strip()
    unit = str(item.get("unit") or "").strip()
    labels = item.get("labels") if isinstance(item.get("labels"), dict) else {}

    def reader_label(key: str, fallback: str) -> str:
        return str(labels.get(key) or fallback).strip()

    meta_items = [
        (reader_label("denominator", "统计对象"), item.get("denominator")),
        (reader_label("scope", "适用场景"), item.get("scope")),
        (reader_label("period", "统计时间"), item.get("period")),
    ]
    meta = "".join(
        '<div class="number-meta-item">'
        f'<dt>{_esc(label)}</dt><dd>{_esc(content)}</dd></div>'
        for label, content in meta_items if content
    )
    baseline = str(item.get("baseline") or "").strip()
    change = str(item.get("change") or "").strip()
    empty_comparison_values = {
        "", "未知", "未提供", "无", "不适用", "无明确对照", "无可计算变化", "无法计算",
    }
    compact = (
        str(item.get("display_variant") or "").strip().lower() == "compact"
        or (baseline in empty_comparison_values and change in empty_comparison_values)
    )
    compare = ""
    if baseline or change:
        compare_parts = []
        if baseline:
            compare_parts.append(
                '<div class="number-compare-item"><div class="number-compare-label">'
                f'{_esc(reader_label("baseline", "对照情况"))}</div>'
                f'<div class="number-compare-value">{_esc(baseline)}</div></div>'
            )
        if baseline and change:
            compare_parts.append('<div class="number-compare-arrow" aria-hidden="true">↓</div>')
        if change:
            compare_parts.append(
                '<div class="number-compare-item"><div class="number-compare-label">'
                f'{_esc(reader_label("change", "结果变化"))}</div>'
                f'<div class="number-compare-value">{_esc(change)}</div></div>'
            )
        compare = f'<div class="number-compare">{"".join(compare_parts)}</div>'
    boundary = str(item.get("boundary") or "").strip()
    mode = "stat" if item.get("display_mode") == "stat" and item.get("complete") is True else "prose"
    main = f'<div class="number-main">{_esc(value)}<small>{_esc(unit)}</small></div>' if value else ""
    if compact:
        compact_meta = str(item.get("display_note") or "").strip() or " · ".join(
            f"{label}：{content}"
            for label, content in (
                (reader_label("denominator", "统计对象"), item.get("denominator")),
                (reader_label("period", "统计时间"), item.get("period")),
            )
            if content
        )
        return (
            f'<aside class="number-story {mode} compact" data-number-story-id="{_esc(item.get("id") or "")}">'
            f'<div class="number-compact-head">{main}<div class="number-detail">'
            f'<div class="number-title">{_esc(title)}</div>'
            f'<div class="number-compact-meta">{_esc(compact_meta)}</div></div></div>'
            f'<div class="number-boundary"><strong>{_esc(reader_label("boundary", "需要注意"))}：</strong>'
            f'{_esc(boundary)}</div></aside>'
        )
    return (
        f'<aside class="number-story {mode}" data-number-story-id="{_esc(item.get("id") or "")}">'
        f'{main}<div class="number-detail"><div class="number-title">{_esc(title)}</div>'
        f'<dl class="number-meta">{meta}</dl>{compare}'
        f'<div class="number-boundary">{_esc(reader_label("boundary", "这个数字不能说明什么"))}：'
        f'{_esc(boundary)}</div></div></aside>'
    )


def _render_listening_card(card: dict) -> str:
    """Render registered audio as a prompt-led, evidence-bounded listening experience."""
    tracks = [
        track for track in (card.get("tracks") or [])
        if isinstance(track, dict) and track.get("registered") is True and track.get("url")
    ]
    if not tracks:
        return ""
    card_id = str(card.get("id") or "listening-card").strip()
    parts = [f'<section class="listening-card" data-listening-card data-listening-card-id="{_esc(card_id)}">']
    parts.append('<div class="listening-head">')
    parts.append(f'<h3 class="listening-title">{_esc(card.get("title") or "听一听模型真正做出了什么")}</h3>')
    if card.get("intro"):
        parts.append(f'<p class="listening-intro">{_esc(card.get("intro"))}</p>')
    parts.append('</div><div class="listening-tabs" role="tablist" aria-label="切换试听样曲">')
    for index, track in enumerate(tracks):
        active = " active" if index == 0 else ""
        selected = "true" if index == 0 else "false"
        tabindex = "0" if index == 0 else "-1"
        tab_id = f"{card_id}-tab-{index + 1}"
        panel_id = f"{card_id}-panel-{index + 1}"
        parts.append(
            f'<button type="button" class="listening-tab{active}" id="{_esc(tab_id)}" role="tab" '
            f'data-listening-tab="{index}" aria-controls="{_esc(panel_id)}" aria-selected="{selected}" tabindex="{tabindex}">'
            f'{_esc(track.get("label") or f"样曲 {index + 1}")}</button>'
        )
    parts.append('</div>')
    for index, track in enumerate(tracks):
        hidden = "" if index == 0 else " hidden"
        tab_id = f"{card_id}-tab-{index + 1}"
        panel_id = f"{card_id}-panel-{index + 1}"
        parts.append(
            f'<div class="listening-panel" id="{_esc(panel_id)}" role="tabpanel" '
            f'data-listening-panel="{index}" aria-labelledby="{_esc(tab_id)}"{hidden}>'
        )
        parts.append(
            f'<audio controls preload="none" data-listening-audio src="{_esc(track.get("url"))}">'
            '当前浏览器无法播放这段音频。</audio>'
        )
        parts.append(
            '<div class="listening-prompt"><span class="listening-label">生成提示词</span>'
            f'{_esc(track.get("prompt") or "未提供")}</div>'
        )
        points = [str(point).strip() for point in (track.get("listening_points") or []) if str(point).strip()]
        if points:
            parts.append('<span class="listening-label">重点听什么</span><ul class="listening-points">')
            parts.extend(f'<li>{_esc(point)}</li>' for point in points)
            parts.append('</ul>')
        if track.get("lyrics_excerpt"):
            parts.append(
                '<details class="listening-lyrics"><summary>歌词摘录</summary>'
                f'<p>{_esc(track.get("lyrics_excerpt"))}</p></details>'
            )
        parts.append('</div>')
    if card.get("boundary"):
        parts.append(f'<p class="listening-boundary">边界：{_esc(card.get("boundary"))}</p>')
    parts.append('</section>')
    return "".join(parts)

