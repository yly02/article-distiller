"""成稿结构门禁。"""
from __future__ import annotations

from typing import Any, Iterable

from language_quality import find_language_issues

from .assets import collect_asset_findings
from .semantics import semantic_claim_coverage
from .structure import collect_structure_findings
from .support import *  # noqa: F403


def audit_distilled(
    distilled: dict,
    research: dict | None = None,
    required_modes: Iterable[str] = ("full",),
    strict_editorial: bool = False,
    semantic_coverage_strict: bool | None = None,
) -> dict:
    """返回确定性质量报告，不修改输入。"""
    modes = {x for x in required_modes if x in OUTPUT_MODES}
    blockers: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}

    if not isinstance(distilled, dict):
        return {
            "publishable": False,
            "score": 0,
            "blockers": ["解读结果顶层不是 JSON 对象"],
            "warnings": [],
            "metrics": {},
        }

    quality_meta = (
        distilled.get("editorial_quality")
        if isinstance(distilled.get("editorial_quality"), dict)
        else {}
    )
    semantic_review_status = _text(quality_meta.get("status")) or "missing"
    semantic_review_completed = semantic_review_status == "completed"
    metrics["semantic_review_status"] = semantic_review_status
    metrics["semantic_review_completed"] = semantic_review_completed
    if not semantic_review_completed:
        warnings.append(
            "未记录已完成的语义级编辑审校；确定性语言规则只能排查高置信问题，不能据此宣称语病检查完整通过"
        )

    research = research if isinstance(research, dict) else {}
    claims = [x for x in _list(research.get("claims")) if isinstance(x, dict)]
    research_claim_ids = {
        _text(x.get("id")) for x in claims if _text(x.get("id"))
    }

    if not _text(distilled.get("distilled_title")):
        blockers.append("缺少 distilled_title")

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
    human_strategy_fields = (
        "opening_anchor",
        "reader_stake",
        "resonance_basis",
        "stance",
    )
    missing_human_strategy_fields = [
        field for field in human_strategy_fields
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
    title_contract_fields = (
        "recognition_anchor",
        "click_reason",
        "reader_promise",
        "evidence_guardrail",
    )
    missing_title_contract_fields = [
        field for field in title_contract_fields if not _text(title_contract.get(field))
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
    if "full" in modes and not narrative_complete:
        message = "缺少完整 narrative_plan，无法审计开头问题是否在结尾得到回答"
        (blockers if strict_editorial else warnings).append(message)
    if "full" in modes and narrative_complete and not human_narrative_complete:
        message = "narrative_plan 缺少 reader_tension 或 core_mechanism，无法完整审计读者张力与单一主线"
        (blockers if strict_editorial else warnings).append(message)
    if "full" in modes and narrative_complete and missing_human_strategy_fields:
        warnings.append(
            "narrative_plan 缺少人味策划字段，仅能按旧稿兼容："
            + ", ".join(missing_human_strategy_fields)
        )
    if "full" in modes and narrative_complete and missing_title_contract_fields:
        warnings.append(
            "narrative_plan.title_contract 不完整，仅能按旧稿兼容："
            + ", ".join(missing_title_contract_fields)
        )
    if "full" in modes and narrative_complete and missing_opening_sequence_fields:
        warnings.append(
            "narrative_plan.opening_sequence 不完整，仅能按旧稿兼容："
            + ", ".join(missing_opening_sequence_fields)
        )
    if "full" in modes and narrative_complete and not chapter_system_complete:
        details = []
        if not _text(chapter_system.get("archetype")):
            details.append("缺 archetype")
        if not _text(chapter_system.get("throughline")):
            details.append("缺 throughline")
        if missing_chapter_section_ids:
            details.append(f"漏章节 {missing_chapter_section_ids}")
        if unknown_chapter_section_ids:
            details.append(f"未知章节 {unknown_chapter_section_ids}")
        if incomplete_chapter_indexes:
            details.append(f"不完整计划 {incomplete_chapter_indexes}")
        if not chapter_entries:
            details.append("缺 chapters")
        warnings.append("narrative_plan.chapter_system 不完整，仅能按旧稿兼容：" + "；".join(details))

    if "full" in modes:
        extra_blockers, extra_warnings, extra_metrics = collect_structure_findings(
            distilled, strict_editorial=strict_editorial
        )
        blockers.extend(extra_blockers)
        warnings.extend(extra_warnings)
        metrics.update(extra_metrics)

    high_ids = {
        _text(x.get("id"))
        for x in claims
        if _text(x.get("id")) and _text(x.get("importance")).lower() == "high"
    }
    coverage = distilled.get("editorial_coverage") if isinstance(distilled.get("editorial_coverage"), dict) else {}
    covered_ids = _claim_ids(_list(coverage.get("covered_claim_ids")))
    omissions = _list(coverage.get("omitted_claims"))
    valid_omissions = [
        x for x in omissions
        if isinstance(x, dict) and _text(x.get("id") or x.get("claim_id")) and _text(x.get("reason"))
    ]
    invalid_omissions = [
        x for x in omissions
        if not isinstance(x, dict) or not _text(x.get("id") or x.get("claim_id")) or not _text(x.get("reason"))
    ]
    omitted_ids = _claim_ids(valid_omissions)
    missing_ids = sorted(high_ids - covered_ids - omitted_ids)
    metrics.update({
        "high_priority_claims": len(high_ids),
        "covered_high_priority_claims": len(high_ids & covered_ids),
        "omitted_high_priority_claims": len(high_ids & omitted_ids),
        "missing_high_priority_claim_ids": missing_ids,
    })
    if high_ids and missing_ids:
        blockers.append(f"高优先级主张未覆盖且未说明舍弃原因：{missing_ids}")
    if high_ids and not coverage:
        blockers.append("有高优先级研究主张，但缺少 editorial_coverage")
    if invalid_omissions:
        blockers.append("omitted_claims 中存在缺少 claim id 或具体 reason 的条目")

    semantic_audit = semantic_claim_coverage(distilled, research, modes)
    semantic_missing = semantic_audit["semantically_missing_high_claim_ids"]
    metrics["semantic_claim_coverage"] = semantic_audit
    metrics["semantically_missing_high_claim_ids"] = semantic_missing
    if semantic_audit["uncheckable_high_claim_ids"]:
        warnings.append(
            "高优先级主张缺少可检查的 claim 文本："
            f"{semantic_audit['uncheckable_high_claim_ids']}"
        )
    if semantic_missing:
        details = [
            f"{mode}={claim_ids}"
            for mode, claim_ids in semantic_audit["missing_by_mode"].items()
            if claim_ids
        ]
        message = "高优先级主张未在发布内容中得到语义覆盖：" + "，".join(details)
        enforce_semantic = strict_editorial if semantic_coverage_strict is None else semantic_coverage_strict
        (blockers if enforce_semantic else warnings).append(message)


    if "full" in modes:
        extra_blockers, extra_warnings, extra_metrics = collect_asset_findings(
            distilled, research, strict_editorial=strict_editorial
        )
        blockers.extend(extra_blockers)
        warnings.extend(extra_warnings)
        metrics.update(extra_metrics)

    language_issues = find_language_issues(distilled)
    metrics["language_issue_count"] = len(language_issues)
    metrics["language_issues"] = language_issues
    if language_issues:
        details = [
            f"{item['path']}：{item['message']}（{item['text']}）"
            for item in language_issues[:6]
        ]
        (blockers if strict_editorial else warnings).append(
            "成文语言检查发现高置信语病：" + "；".join(details)
        )

    score = max(0, 100 - len(blockers) * 20 - len(warnings) * 5)
    return {
        "publishable": not blockers,
        "score": score,
        "blockers": blockers,
        "warnings": warnings,
        "metrics": metrics,
    }


def choose_preferred(
    draft: dict,
    revised: dict,
    research: dict | None = None,
    required_modes: Iterable[str] = ("full",),
    strict_editorial: bool = True,
) -> tuple[dict, str, dict, dict]:
    """选择确定性质量更好的版本；分数相同时优先审校后的版本。"""
    draft_audit = audit_distilled(draft, research, required_modes, strict_editorial)
    revised_audit = audit_distilled(revised, research, required_modes, strict_editorial)
    draft_rank = (len(draft_audit["blockers"]), len(draft_audit["warnings"]), -draft_audit["score"])
    revised_rank = (len(revised_audit["blockers"]), len(revised_audit["warnings"]), -revised_audit["score"])
    if revised_rank <= draft_rank:
        return revised, "revised", draft_audit, revised_audit
    return draft, "draft", draft_audit, revised_audit


def assert_publishable(audit: dict, stage: str = "写作结果") -> None:
    blockers = list(audit.get("blockers") or [])
    if blockers:
        raise ValueError(f"{stage}未通过质量门禁：" + "；".join(blockers[:6]))
