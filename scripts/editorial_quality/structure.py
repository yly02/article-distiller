"""完整文章的结构、速览和语气检查。"""
from __future__ import annotations

from typing import Any

from language_quality import analyze_reader_voice

from .semantics import _public_path, _walk_public_text
from .support import *  # noqa: F403


def collect_structure_findings(
    distilled: dict,
    *,
    strict_editorial: bool,
) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    base_quick_scan = [_text(x) for x in _list(distilled.get("quick_scan")) if _text(x)]
    base_sections = [x for x in _list(distilled.get("sections")) if isinstance(x, dict)]
    base_usable_sections = [
        x for x in base_sections if _text(x.get("title")) and _text(x.get("content"))
    ]
    narrative = distilled.get("narrative_plan")
    narrative_complete = (
        isinstance(narrative, dict)
        and _text(narrative.get("central_question"))
        and _text(narrative.get("closing_answer"))
    )
    human_narrative_complete = (
        isinstance(narrative, dict)
        and _text(narrative.get("reader_tension"))
        and _text(narrative.get("core_mechanism"))
    )
    missing_human_strategy_fields = [
        field for field in ("opening_anchor", "reader_stake", "resonance_basis", "stance")
        if not isinstance(narrative, dict) or not _text(narrative.get(field))
    ]
    title_contract = narrative.get("title_contract") if isinstance(narrative, dict) else {}
    title_contract = title_contract if isinstance(title_contract, dict) else {}
    title_text_normalized = _normalized_text(distilled.get("distilled_title")).casefold()
    recognition_anchor_normalized = _normalized_text(
        title_contract.get("recognition_anchor")
    ).casefold()
    title_anchor_index = (
        title_text_normalized.find(recognition_anchor_normalized)
        if recognition_anchor_normalized else -1
    )
    title_anchor_in_front_half = bool(
        recognition_anchor_normalized
        and title_anchor_index >= 0
        and title_anchor_index <= max(0, len(title_text_normalized) // 2)
    )
    missing_title_contract_fields = [
        field for field in ("recognition_anchor", "click_reason", "reader_promise", "evidence_guardrail")
        if not _text(title_contract.get(field))
    ]
    opening_sequence = narrative.get("opening_sequence") if isinstance(narrative, dict) else {}
    opening_sequence = opening_sequence if isinstance(opening_sequence, dict) else {}
    missing_opening_sequence_fields = [
        field for field in ("scene", "turn", "reveal")
        if not _text(opening_sequence.get(field))
    ]
    chapter_system = narrative.get("chapter_system") if isinstance(narrative, dict) else {}
    chapter_system = chapter_system if isinstance(chapter_system, dict) else {}
    chapter_entries = [
        item for item in _list(chapter_system.get("chapters")) if isinstance(item, dict)
    ]
    section_ids = {_text(item.get("id")) for item in base_usable_sections if _text(item.get("id"))}
    chapter_section_ids = {
        _text(item.get("section_id")) for item in chapter_entries if _text(item.get("section_id"))
    }
    missing_chapter_section_ids = sorted(section_ids - chapter_section_ids)
    unknown_chapter_section_ids = sorted(chapter_section_ids - section_ids)
    incomplete_chapter_indexes = [
        index + 1
        for index, item in enumerate(chapter_entries)
        if not all(_text(item.get(field)) for field in ("section_id", "role", "reader_need", "advance", "evidence"))
    ]
    chapter_system_complete = bool(
        _text(chapter_system.get("archetype"))
        and _text(chapter_system.get("throughline"))
        and chapter_entries
        and not missing_chapter_section_ids
        and not unknown_chapter_section_ids
        and not incomplete_chapter_indexes
    )
    quick_scan = base_quick_scan
    category_tags = [
        _text(item) for item in _list(distilled.get("category_tags")) if _text(item)
    ]
    duplicate_category_tags = sorted({
        tag for tag in category_tags if category_tags.count(tag) > 1
    })
    long_category_tag_indexes = [
        index + 1
        for index, tag in enumerate(category_tags)
        if len(tag) > (12 if all(ord(char) < 128 for char in tag) else 8)
    ]
    sections = base_sections
    usable_sections = base_usable_sections
    empty_sections = [i + 1 for i, x in enumerate(sections) if not _text(x.get("title")) or not _text(x.get("content"))]
    duplicates = _duplicate_pairs(usable_sections, "title", "content")
    placeholder_sections = [
        i + 1 for i, x in enumerate(sections)
        if _is_placeholder(x.get("title")) or _is_placeholder(x.get("content"))
    ]
    thin_sections = [
        i + 1 for i, x in enumerate(usable_sections)
        if len(_normalized_text(x.get("content"))) < 30
    ]
    meta_narration_sections = [
        i + 1 for i, x in enumerate(usable_sections)
        if META_NARRATION_RE.search(_text(x.get("content")))
    ]
    meta_narration_public_paths = []
    for field in (
        "quick_scan", "one_liner", "recommendation_reason", "experiment_ledger",
        "case_stories", "number_stories", "visuals", "action_card", "takeaway_list",
    ):
        for path, value in _walk_public_text(distilled.get(field), (field,)):
            if META_NARRATION_RE.search(value):
                meta_narration_public_paths.append(_public_path(path))
    public_audit_tone_paths = []
    for field in (
        "quick_scan", "one_liner", "recommendation_reason", "sections",
        "experiment_ledger", "case_stories", "number_stories", "visuals",
        "action_card", "takeaway_list",
    ):
        for path, value in _walk_public_text(distilled.get(field), (field,)):
            if PUBLIC_AUDIT_TONE_RE.search(value):
                public_audit_tone_paths.append(_public_path(path))
    original_quote_count = sum(
        1
        for section in sections
        for quote in _list(section.get("archive_original"))
        if isinstance(quote, dict)
        and (_text(quote.get("original")) or _text(quote.get("translation")))
    )
    metrics.update({
        "quick_scan_count": len(quick_scan),
        "quick_scan_char_count": _char_count(*quick_scan),
        "quick_scan_item_char_counts": [_char_count(item) for item in quick_scan],
        "category_tag_count": len(category_tags),
        "duplicate_category_tags": duplicate_category_tags,
        "long_category_tag_indexes": long_category_tag_indexes,
        "section_count": len(usable_sections),
        "empty_section_indexes": empty_sections,
        "duplicate_sections": duplicates,
        "placeholder_section_indexes": placeholder_sections,
        "thin_section_indexes": thin_sections,
        "meta_narration_section_indexes": meta_narration_sections,
        "meta_narration_public_paths": meta_narration_public_paths,
        "public_audit_tone_paths": public_audit_tone_paths,
        "original_quote_count": original_quote_count,
        "human_narrative_complete": human_narrative_complete,
        "missing_human_strategy_fields": missing_human_strategy_fields,
        "missing_title_contract_fields": missing_title_contract_fields,
        "title_recognition_anchor": _text(title_contract.get("recognition_anchor")),
        "title_anchor_in_front_half": title_anchor_in_front_half,
        "missing_opening_sequence_fields": missing_opening_sequence_fields,
        "chapter_system_complete": chapter_system_complete,
        "missing_chapter_section_ids": missing_chapter_section_ids,
        "unknown_chapter_section_ids": unknown_chapter_section_ids,
        "incomplete_chapter_indexes": incomplete_chapter_indexes,
    })
    if len(quick_scan) != 3:
        (blockers if strict_editorial else warnings).append(
            f"一分钟导览有 {len(quick_scan)} 条，必须精简为 3 条"
        )
    quick_scan_chars = _char_count(*quick_scan)
    if quick_scan_chars > 180:
        (blockers if strict_editorial else warnings).append(
            f"一分钟导览共 {quick_scan_chars} 字，必须压缩到 180 字以内"
        )
    long_quick_scan = [
        i + 1 for i, item in enumerate(quick_scan) if _char_count(item) > 70
    ]
    if long_quick_scan:
        warnings.append(f"一分钟导览单条超过 70 字：{long_quick_scan}")
    if category_tags and not 3 <= len(category_tags) <= 5:
        (blockers if strict_editorial else warnings).append(
            f"归档标签有 {len(category_tags)} 个，必须保留 3-5 个稳定大类"
        )
    if duplicate_category_tags:
        (blockers if strict_editorial else warnings).append(
            f"归档标签存在重复项：{duplicate_category_tags}"
        )
    if long_category_tag_indexes:
        (blockers if strict_editorial else warnings).append(
            "归档标签必须短平快，中文不超过 8 字、纯英文不超过 12 字符："
            f"{long_category_tag_indexes}"
        )
    if recognition_anchor_normalized and not title_anchor_in_front_half:
        (blockers if strict_editorial else warnings).append(
            "标题未在前半句兑现 title_contract.recognition_anchor："
            f"{_text(title_contract.get('recognition_anchor'))}"
        )
    if len(usable_sections) < 3:
        blockers.append(f"完整正文只有 {len(usable_sections)} 个有效段落，至少需要 3 个")
    if empty_sections:
        blockers.append(f"正文存在标题或内容为空的段落：{empty_sections}")
    if duplicates:
        blockers.append(f"正文存在高度重复段落：{duplicates}")
    if placeholder_sections:
        blockers.append(f"正文存在占位内容：{placeholder_sections}")
    if thin_sections:
        warnings.append(f"正文段落信息量偏低：{thin_sections}")
    if meta_narration_sections:
        (blockers if strict_editorial else warnings).append(
            f"正文存在割裂的研究过程话术，请改为独立文章语气：{meta_narration_sections}"
        )
    if meta_narration_public_paths:
        (blockers if strict_editorial else warnings).append(
            "发布内容存在写作过程自述，请改为直接面向读者的自然表达："
            f"{meta_narration_public_paths}"
        )
    if public_audit_tone_paths:
        warnings.append(
            "公开内容出现审计式过程或验证口吻；请把必要边界改写成贴近事实的普通表达，其余信息留在后台："
            f"{public_audit_tone_paths}"
        )
    if original_quote_count > 2:
        (blockers if strict_editorial else warnings).append(
            f"原文引文有 {original_quote_count} 条，最多保留 2 条措辞不可替代的引文"
        )
    if narrative_complete:
        section_logic = [_text(x) for x in _list(narrative.get("section_logic")) if _text(x)]
        if len(section_logic) < len(usable_sections):
            warnings.append(
                f"narrative_plan 只解释了 {len(section_logic)} 段关系，正文有 {len(usable_sections)} 段"
            )

    reader_voice = analyze_reader_voice(distilled)
    metrics["reader_voice"] = reader_voice
    dense_sections = reader_voice["dense_section_indexes"]
    long_sentences = reader_voice["long_sentences"]
    stiff_hits = reader_voice["stiff_phrase_hits"]
    antithesis_count = reader_voice["antithesis_count"]
    proxy_reader_hits = reader_voice["proxy_reader_hits"]
    performative_depth_hits = reader_voice["performative_depth_hits"]
    abstract_action_hits = reader_voice["abstract_action_hits"]
    uniform_rhythm_sections = reader_voice["uniform_rhythm_section_indexes"]
    question_dense_sections = reader_voice["question_dense_section_indexes"]
    if len(dense_sections) >= 2:
        warnings.append(
            f"正文存在连续文字墙，建议按判断、事实、解释或边界自然分段：{dense_sections}"
        )
    if len(long_sentences) >= 3:
        warnings.append(
            f"正文有 {len(long_sentences)} 个超过 72 个汉字的长句，建议在不丢条件的前提下调整节奏"
        )
    if sum(item["count"] for item in stiff_hits) >= 2:
        phrases = list(dict.fromkeys(item["phrase"] for item in stiff_hits))
        warnings.append(f"正文报告套话重复出现，建议改成具体判断：{phrases}")
    if antithesis_count >= 4:
        warnings.append(
            f"全文使用 {antithesis_count} 次转折对举句式，建议改变起句和论证节奏"
        )
    if len(proxy_reader_hits) >= 3:
        warnings.append(
            f"正文有 {len(proxy_reader_hits)} 处替读者预设想法，建议只保留真实异议并先准确复述其合理版本"
        )
    if len(performative_depth_hits) >= 3:
        warnings.append(
            f"正文有 {len(performative_depth_hits)} 处仪式化深刻表达，建议保留核心判断并删除无必要升华"
        )
    if abstract_action_hits:
        warnings.append(
            f"公开标题或卡片有 {len(abstract_action_hits)} 处抽象动作，建议写清谁完成了调查、处理或验证："
            f"{[item['text'] for item in abstract_action_hits]}"
        )
    if len(uniform_rhythm_sections) >= 2:
        warnings.append(
            f"正文多个章节句长过于均匀，建议用自然长短句调整阅读呼吸：{uniform_rhythm_sections}"
        )
    if question_dense_sections:
        warnings.append(
            f"正文部分章节连续抛出三个以上问题，建议先回答再推进：{question_dense_sections}"
        )


    return blockers, warnings, metrics
