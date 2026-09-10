"""实验、案例、视觉组件和媒体登记检查。"""
from __future__ import annotations

from typing import Any

from .support import *  # noqa: F403


def collect_asset_findings(
    distilled: dict,
    research: dict,
    *,
    strict_editorial: bool,
) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    claims = [x for x in _list(research.get("claims")) if isinstance(x, dict)]
    research_claim_ids = {_text(x.get("id")) for x in claims if _text(x.get("id"))}
    base_sections = [x for x in _list(distilled.get("sections")) if isinstance(x, dict)]
    research_experiments = [
        x for x in _list(research.get("experiments")) if isinstance(x, dict)
    ]
    research_cases = [x for x in _list(research.get("cases")) if isinstance(x, dict)]
    experiments = [
        x for x in _list(distilled.get("experiment_ledger")) if isinstance(x, dict)
    ]
    case_stories = [
        x for x in _list(distilled.get("case_stories")) if isinstance(x, dict)
    ]
    visuals = [x for x in _list(distilled.get("visuals")) if isinstance(x, dict)]
    valid_experiments = [x for x in experiments if _valid_experiment(x)]
    valid_cases = [x for x in case_stories if _valid_case_story(x)]
    section_ids = {_text(x.get("id")) for x in base_sections if _text(x.get("id"))}
    high_experiment_ids = {
        _text(x.get("id")) for x in research_experiments
        if _text(x.get("id")) and _text(x.get("importance")).lower() == "high"
    }
    high_case_ids = {
        _text(x.get("id")) for x in research_cases
        if _text(x.get("id")) and _text(x.get("importance")).lower() == "high"
    }
    output_experiment_ids = {_text(x.get("id")) for x in valid_experiments}
    output_case_ids = {_text(x.get("id")) for x in valid_cases}
    missing_experiments = sorted(high_experiment_ids - output_experiment_ids)
    missing_cases = sorted(high_case_ids - output_case_ids)
    invalid_experiment_indexes = [
        i + 1 for i, item in enumerate(experiments) if not _valid_experiment(item)
    ]
    invalid_case_indexes = [
        i + 1 for i, item in enumerate(case_stories) if not _valid_case_story(item)
    ]
    invalid_interactive_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "interactive_compare"
        and not _valid_interactive_compare(item)
    ]
    invalid_interactive_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "interactive_compare"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_strategy_tab_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "strategy_tabs"
        and not _valid_strategy_tabs(item)
    ]
    invalid_strategy_tab_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "strategy_tabs"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_scenario_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "scenario_calculator"
        and not _valid_scenario_calculator(item)
    ]
    invalid_scenario_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "scenario_calculator"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_capacity_curve_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "capacity_curve"
        and not _valid_capacity_curve(item)
    ]
    invalid_capacity_curve_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "capacity_curve"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_cost_ledger_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "cost_ledger"
        and not _valid_cost_ledger(item)
    ]
    invalid_cost_ledger_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "cost_ledger"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_metric_bar_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "metric_bars"
        and not _valid_metric_bars(item)
    ]
    invalid_metric_bar_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "metric_bars"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_rank_bar_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "rank_bars"
        and not _valid_rank_bars(item)
    ]
    invalid_rank_bar_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "rank_bars"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_funnel_flow_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "funnel_flow"
        and not _valid_funnel_flow(item)
    ]
    invalid_funnel_flow_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "funnel_flow"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_delta_table_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "delta_table"
        and not _valid_delta_table(item)
    ]
    invalid_delta_table_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "delta_table"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_status_matrix_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "status_matrix"
        and not _valid_status_matrix(item)
    ]
    invalid_status_matrix_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "status_matrix"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_decision_table_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "decision_table"
        and not _valid_decision_table(item)
    ]
    invalid_decision_table_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "decision_table"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_flow_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "flow"
        and not _valid_flow_visual(item)
    ]
    invalid_flow_stepper_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "flow"
        and isinstance(item.get("data"), dict)
        and _text(item["data"].get("presentation")).lower() == "stepper"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_timeline_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "timeline"
        and not _valid_timeline_visual(item)
    ]
    invalid_timeline_scrubber_anchors = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "timeline"
        and isinstance(item.get("data"), dict)
        and _text(item["data"].get("presentation")).lower() == "scrubber"
        and _text(item.get("after_section_id")) not in section_ids
    ]
    invalid_layer_stack_indexes = [
        i + 1 for i, item in enumerate(visuals)
        if _text(item.get("type")).lower() == "layer_stack"
        and not _valid_layer_stack(item)
    ]
    oversized_matrix_indexes = []
    for i, item in enumerate(visuals):
        if _text(item.get("type")).lower() != "compare_table":
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        if _text(data.get("layout")).lower() != "matrix":
            continue
        headers = _list(data.get("headers"))
        rows = _list(data.get("rows"))
        if len(rows) > 6 or len(headers) > 4 or len(rows) * len(headers) > 24:
            oversized_matrix_indexes.append(i + 1)
    bad_anchors = [
        f"experiment:{_text(item.get('id')) or i + 1}"
        for i, item in enumerate(valid_experiments)
        if _text(item.get("after_section_id")) not in section_ids
    ] + [
        f"case:{_text(item.get('id')) or i + 1}"
        for i, item in enumerate(valid_cases)
        if _text(item.get("after_section_id")) not in section_ids
    ]
    unknown_claim_refs = sorted({
        ref
        for item in valid_experiments + valid_cases
        for ref in _claim_ids(_list(item.get("claim_ids")))
        if ref not in research_claim_ids
    })
    source_media = [
        item for item in _list(distilled.get("source_media")) if isinstance(item, dict)
    ]
    invalid_media_indexes = [
        i + 1 for i, item in enumerate(source_media)
        if not all(_has_content(item.get(key)) for key in ("media_id", "type", "url", "after_section_id"))
        or _text(item.get("type")).lower() not in {"image", "video"}
    ]
    invalid_media_anchors = [
        _text(item.get("media_id")) or str(i + 1)
        for i, item in enumerate(source_media)
        if _text(item.get("after_section_id")) not in section_ids
    ]
    unregistered_media = [
        _text(item.get("media_id")) or str(i + 1)
        for i, item in enumerate(source_media)
        if item.get("registered") is False
    ]
    media_urls = [_text(item.get("url")) for item in source_media if _text(item.get("url"))]
    duplicate_media_urls = sorted({url for url in media_urls if media_urls.count(url) > 1})
    foreign_media_without_guidance = [
        _text(item.get("media_id")) or str(i + 1)
        for i, item in enumerate(source_media)
        if _text(item.get("language")).lower() not in {"", "zh", "zh-cn", "zh-hans", "chinese"}
        and (
            not re.search(r"[\u3400-\u9fff]", _text(item.get("caption")))
            or not re.search(r"[\u3400-\u9fff]", _text(item.get("reader_note")))
        )
    ]
    media_explanation_gaps = [
        _text(item.get("media_id")) or str(i + 1)
        for i, item in enumerate(source_media)
        if not _text(item.get("purpose"))
        or not _text(item.get("reader_note"))
        or len(_text(item.get("reader_note"))) < 8
    ]
    media_policy = distilled.get("media_policy") if isinstance(distilled.get("media_policy"), dict) else {}
    media_discovery = media_policy.get("discovery") if isinstance(media_policy.get("discovery"), dict) else {}
    media_discovery_status = _text(media_discovery.get("status")).lower()
    available_assets = [
        item for item in _list(media_policy.get("available_assets")) if isinstance(item, dict)
    ]
    available_demo_video_ids = [
        _text(item.get("id")) or _text(item.get("url"))
        for item in available_assets
        if _text(item.get("type")).lower() == "video"
        and _text(item.get("asset_role")).lower() in {"demo", "hero"}
    ]
    used_video_ids = {
        _text(item.get("media_id"))
        for item in source_media
        if _text(item.get("type")).lower() == "video" and item.get("registered") is True
    }
    media_omissions = [
        item for item in _list(distilled.get("media_omissions")) if isinstance(item, dict)
    ]
    invalid_media_omission_indexes = [
        i + 1 for i, item in enumerate(media_omissions)
        if not _text(item.get("media_id"))
        or len(_text(item.get("reason"))) < 4
        or _is_placeholder(item.get("reason"))
    ]
    unregistered_media_omissions = [
        _text(item.get("media_id")) or str(i + 1)
        for i, item in enumerate(media_omissions)
        if item.get("registered") is not True
    ]
    omitted_video_ids = {
        _text(item.get("media_id"))
        for item in media_omissions
        if item.get("registered") is True
        and _text(item.get("type")).lower() == "video"
        and len(_text(item.get("reason"))) >= 4
        and not _is_placeholder(item.get("reason"))
    }
    conflicting_media_decisions = sorted(used_video_ids & omitted_video_ids)
    duplicate_media_omission_ids = sorted({
        media_id
        for media_id in [_text(item.get("media_id")) for item in media_omissions]
        if media_id and sum(
            1 for item in media_omissions if _text(item.get("media_id")) == media_id
        ) > 1
    })
    unexplained_demo_video_ids = [
        media_id for media_id in available_demo_video_ids
        if media_id not in used_video_ids and media_id not in omitted_video_ids
    ]
    number_stories = [
        item for item in _list(distilled.get("number_stories")) if isinstance(item, dict)
    ]
    visible_number_stories = [
        item for item in number_stories
        if item.get("suppress_visual") is not True
        and _text(item.get("display_mode")).lower() != "audit_only"
    ]
    visible_number_story_count_by_section = {}
    for item in visible_number_stories:
        section_id = _text(item.get("after_section_id"))
        visible_number_story_count_by_section[section_id] = (
            visible_number_story_count_by_section.get(section_id, 0) + 1
        )
    dense_number_story_sections = sorted(
        section_id
        for section_id, count in visible_number_story_count_by_section.items()
        if count > 1
    )
    visual_count_by_section = {}
    for item in visuals:
        section_id = _text(item.get("after_section_id"))
        if section_id:
            visual_count_by_section[section_id] = visual_count_by_section.get(section_id, 0) + 1
    mixed_main_visual_sections = sorted(
        section_id
        for section_id in visible_number_story_count_by_section
        if visual_count_by_section.get(section_id, 0) > 0
    )
    high_metric_ids = {
        _text(item.get("id"))
        for item in claims
        if _text(item.get("id"))
        and _text(item.get("importance")).lower() == "high"
        and _text(item.get("claim_kind")).lower() == "metric"
    }
    story_claim_ids = {
        claim_id
        for item in number_stories
        for claim_id in _claim_ids(_list(item.get("claim_ids")))
    }
    missing_metric_story_ids = sorted(high_metric_ids - story_claim_ids)
    incomplete_number_story_ids = []
    invalid_number_story_anchors = []
    unknown_number_story_claim_ids = set()
    unregistered_number_story_assets = set()
    unregistered_number_story_sources = []
    incomplete_high_metric_ids = set()
    for index, item in enumerate(number_stories):
        story_id = _text(item.get("id")) or str(index + 1)
        labels = item.get("labels") if isinstance(item.get("labels"), dict) else {}
        has_context = lambda key: (  # noqa: E731
            _known_number_context(item.get(key))
            or _known_number_context(labels.get(key))
        )
        has_change = _known_number_context(item.get("baseline")) or _known_number_context(item.get("change"))
        has_source = _has_content(item.get("source_url")) or bool(_list(item.get("source_asset_ids")))
        structurally_complete = (
            all(has_context(key) for key in ("value", "unit", "denominator", "scope", "period", "boundary"))
            and has_change
            and has_source
        )
        complete = item.get("complete") is True if "complete" in item else structurally_complete
        if not complete:
            incomplete_number_story_ids.append(story_id)
            incomplete_high_metric_ids.update(
                claim_id
                for claim_id in _claim_ids(_list(item.get("claim_ids")))
                if claim_id in high_metric_ids
            )
        if _text(item.get("after_section_id")) not in section_ids:
            invalid_number_story_anchors.append(story_id)
        unknown_number_story_claim_ids.update(
            claim_id
            for claim_id in _claim_ids(_list(item.get("claim_ids")))
            if research_claim_ids and claim_id not in research_claim_ids
        )
        unregistered_number_story_assets.update(_list(item.get("unregistered_source_asset_ids")))
        if item.get("source_url") and item.get("source_registered") is False:
            unregistered_number_story_sources.append(story_id)
    incomplete_high_metric_ids = sorted(incomplete_high_metric_ids)
    evidence_gallery = [
        item for item in _list(distilled.get("evidence_gallery")) if isinstance(item, dict)
    ]
    invalid_gallery_items = [
        i + 1 for i, item in enumerate(evidence_gallery)
        if item.get("registered") is False
        or not _has_content(item.get("media_id"))
        or (_has_content(item.get("type")) and _text(item.get("type")).lower() not in {"image", "video"})
    ]
    gallery_urls = [_text(item.get("url")) for item in evidence_gallery if _text(item.get("url"))]
    duplicate_gallery_urls = sorted({url for url in gallery_urls if gallery_urls.count(url) > 1})
    gallery_media_ids = {
        _text(item.get("media_id")) for item in evidence_gallery if _text(item.get("media_id"))
    }
    scenario_source_asset_ids = {
        media_id
        for item in visuals
        if _text(item.get("type")).lower() == "scenario_calculator"
        for media_id in _claim_ids(_list(
            item.get("data", {}).get("source_asset_ids")
            if isinstance(item.get("data"), dict) else []
        ))
    }
    unregistered_scenario_assets = sorted(scenario_source_asset_ids - gallery_media_ids)
    listening_cards = [
        item for item in _list(distilled.get("listening_cards")) if isinstance(item, dict)
    ]
    invalid_listening_cards = []
    invalid_listening_anchors = []
    unregistered_listening_tracks = []
    for card_index, card in enumerate(listening_cards):
        card_id = _text(card.get("id")) or str(card_index + 1)
        tracks = [track for track in _list(card.get("tracks")) if isinstance(track, dict)]
        valid_tracks = [
            track for track in tracks
            if all(_has_content(track.get(key)) for key in ("media_id", "url", "label", "prompt"))
            and bool(_list(track.get("listening_points")))
        ]
        if (
            not all(_has_content(card.get(key)) for key in ("id", "title", "after_section_id", "boundary"))
            or not tracks
            or len(valid_tracks) != len(tracks)
        ):
            invalid_listening_cards.append(card_id)
        if _text(card.get("after_section_id")) not in section_ids:
            invalid_listening_anchors.append(card_id)
        unregistered_listening_tracks.extend(
            f"{card_id}:{_text(track.get('media_id')) or index + 1}"
            for index, track in enumerate(tracks)
            if track.get("registered") is not True or _text(track.get("type")).lower() != "audio"
        )
    metrics.update({
        "research_experiment_count": len(research_experiments),
        "article_experiment_count": len(valid_experiments),
        "missing_high_experiment_ids": missing_experiments,
        "research_case_count": len(research_cases),
        "article_case_count": len(valid_cases),
        "missing_high_case_ids": missing_cases,
        "invalid_experiment_indexes": invalid_experiment_indexes,
        "invalid_case_indexes": invalid_case_indexes,
        "invalid_interactive_visual_indexes": invalid_interactive_indexes,
        "invalid_interactive_visual_anchors": invalid_interactive_anchors,
        "invalid_strategy_tab_indexes": invalid_strategy_tab_indexes,
        "invalid_strategy_tab_anchors": invalid_strategy_tab_anchors,
        "invalid_scenario_visual_indexes": invalid_scenario_indexes,
        "invalid_scenario_visual_anchors": invalid_scenario_anchors,
        "invalid_capacity_curve_indexes": invalid_capacity_curve_indexes,
        "invalid_capacity_curve_anchors": invalid_capacity_curve_anchors,
        "invalid_cost_ledger_indexes": invalid_cost_ledger_indexes,
        "invalid_cost_ledger_anchors": invalid_cost_ledger_anchors,
        "invalid_metric_bar_indexes": invalid_metric_bar_indexes,
        "invalid_metric_bar_anchors": invalid_metric_bar_anchors,
        "invalid_rank_bar_indexes": invalid_rank_bar_indexes,
        "invalid_rank_bar_anchors": invalid_rank_bar_anchors,
        "invalid_funnel_flow_indexes": invalid_funnel_flow_indexes,
        "invalid_funnel_flow_anchors": invalid_funnel_flow_anchors,
        "invalid_delta_table_indexes": invalid_delta_table_indexes,
        "invalid_delta_table_anchors": invalid_delta_table_anchors,
        "invalid_status_matrix_indexes": invalid_status_matrix_indexes,
        "invalid_status_matrix_anchors": invalid_status_matrix_anchors,
        "invalid_decision_table_indexes": invalid_decision_table_indexes,
        "invalid_decision_table_anchors": invalid_decision_table_anchors,
        "invalid_flow_visual_indexes": invalid_flow_indexes,
        "invalid_flow_stepper_anchors": invalid_flow_stepper_anchors,
        "invalid_timeline_visual_indexes": invalid_timeline_indexes,
        "invalid_timeline_scrubber_anchors": invalid_timeline_scrubber_anchors,
        "invalid_layer_stack_indexes": invalid_layer_stack_indexes,
        "oversized_matrix_visual_indexes": oversized_matrix_indexes,
        "unregistered_scenario_source_assets": unregistered_scenario_assets,
        "invalid_content_anchors": bad_anchors,
        "unknown_component_claim_ids": unknown_claim_refs,
        "source_media_count": len(source_media),
        "invalid_source_media_indexes": invalid_media_indexes,
        "invalid_source_media_anchors": invalid_media_anchors,
        "unregistered_source_media": unregistered_media,
        "duplicate_source_media_urls": duplicate_media_urls,
        "foreign_media_without_chinese_guidance": foreign_media_without_guidance,
        "media_explanation_gaps": media_explanation_gaps,
        "available_demo_video_count": len(available_demo_video_ids),
        "used_source_video_count": len(used_video_ids),
        "media_omission_count": len(media_omissions),
        "invalid_media_omission_indexes": invalid_media_omission_indexes,
        "unregistered_media_omissions": unregistered_media_omissions,
        "duplicate_media_omission_ids": duplicate_media_omission_ids,
        "conflicting_media_decisions": conflicting_media_decisions,
        "unused_demo_video_ids": unexplained_demo_video_ids,
        "media_discovery_status": media_discovery_status,
        "number_story_count": len(number_stories),
        "visible_number_story_count": len(visible_number_stories),
        "visible_number_story_count_by_section": visible_number_story_count_by_section,
        "dense_number_story_sections": dense_number_story_sections,
        "mixed_main_visual_sections": mixed_main_visual_sections,
        "missing_high_metric_story_ids": missing_metric_story_ids,
        "incomplete_number_story_ids": incomplete_number_story_ids,
        "incomplete_high_metric_story_claim_ids": incomplete_high_metric_ids,
        "invalid_number_story_anchors": invalid_number_story_anchors,
        "unknown_number_story_claim_ids": sorted(unknown_number_story_claim_ids),
        "unregistered_number_story_assets": sorted(unregistered_number_story_assets),
        "unregistered_number_story_sources": unregistered_number_story_sources,
        "evidence_gallery_count": len(evidence_gallery),
        "invalid_evidence_gallery_items": invalid_gallery_items,
        "duplicate_evidence_gallery_urls": duplicate_gallery_urls,
        "listening_card_count": len(listening_cards),
        "invalid_listening_cards": invalid_listening_cards,
        "invalid_listening_card_anchors": invalid_listening_anchors,
        "unregistered_listening_tracks": unregistered_listening_tracks,
    })
    depth_issues = []
    if missing_experiments:
        depth_issues.append(f"高优先级实验未进入文章：{missing_experiments}")
    if missing_cases:
        depth_issues.append(f"高优先级案例未进入文章：{missing_cases}")
    if invalid_experiment_indexes:
        depth_issues.append(f"实验账本缺少问题、条件、指标、结果、限制或 claim_ids：{invalid_experiment_indexes}")
    if invalid_case_indexes:
        depth_issues.append(f"案例叙事缺少三步事件链、来源模式、结果、边界或 claim_ids：{invalid_case_indexes}")
    if invalid_interactive_indexes:
        depth_issues.append(
            f"机制互动缺少至少两个候选、两个模式、合法 selected_index 或边界说明：{invalid_interactive_indexes}"
        )
    if invalid_interactive_anchors:
        depth_issues.append(f"机制互动指向不存在的 section id：{invalid_interactive_anchors}")
    if invalid_strategy_tab_indexes:
        depth_issues.append(
            "策略切换器需要2至6个完整方案，每项包含作用对象、机制、预期效果、"
            f"待补条件和语义色，并提供阅读边界：{invalid_strategy_tab_indexes}"
        )
    if invalid_strategy_tab_anchors:
        depth_issues.append(f"策略切换器指向不存在的 section id：{invalid_strategy_tab_anchors}")
    if invalid_scenario_indexes:
        depth_issues.append(f"证据情景卡缺少双对象指标、合法滑块、计算基数、来源媒体或边界说明：{invalid_scenario_indexes}")
    if invalid_scenario_anchors:
        depth_issues.append(f"证据情景卡指向不存在的 section id：{invalid_scenario_anchors}")
    if invalid_capacity_curve_indexes:
        depth_issues.append(
            "定性曲线需要3至5个位置递增的状态、合法语义色、坐标含义，"
            f"并明确说明不是通用预测器：{invalid_capacity_curve_indexes}"
        )
    if invalid_capacity_curve_anchors:
        depth_issues.append(f"定性曲线指向不存在的 section id：{invalid_capacity_curve_anchors}")
    if invalid_cost_ledger_indexes:
        depth_issues.append(
            "成本账本需要1至4个成本项、2至6个完整且唯一的情景，"
            f"included 只能引用已登记成本，并提供口径边界：{invalid_cost_ledger_indexes}"
        )
    if invalid_cost_ledger_anchors:
        depth_issues.append(f"成本账本指向不存在的 section id：{invalid_cost_ledger_anchors}")
    if invalid_metric_bar_indexes:
        depth_issues.append(
            f"指标切换卡缺少双方案、至少两组指标、每组两行有效数值、比较方向或阅读边界：{invalid_metric_bar_indexes}"
        )
    if invalid_metric_bar_anchors:
        depth_issues.append(f"指标切换卡指向不存在的 section id：{invalid_metric_bar_anchors}")
    if invalid_rank_bar_indexes:
        depth_issues.append(
            "单口径排名条需要1至4个合法分组、每组2至18项同单位且按绝对值降序的数值，"
            f"并提供方向、语义色和阅读边界：{invalid_rank_bar_indexes}"
        )
    if invalid_rank_bar_anchors:
        depth_issues.append(f"单口径排名条指向不存在的 section id：{invalid_rank_bar_anchors}")
    if invalid_funnel_flow_indexes:
        depth_issues.append(
            "资格漏斗需要2至5道真实收窄关口、入口、每关说明和阅读边界；"
            f"显式宽度必须逐级递减：{invalid_funnel_flow_indexes}"
        )
    if invalid_funnel_flow_anchors:
        depth_issues.append(f"资格漏斗指向不存在的 section id：{invalid_funnel_flow_anchors}")
    if invalid_delta_table_indexes:
        depth_issues.append(
            "前后变化表需要2至8行完整的旧值、新值、变化、方向和语义色，并提供统一阅读边界："
            f"{invalid_delta_table_indexes}"
        )
    if invalid_delta_table_anchors:
        depth_issues.append(f"前后变化表指向不存在的 section id：{invalid_delta_table_anchors}")
    if invalid_status_matrix_indexes:
        depth_issues.append(
            "状态矩阵需要2至6个维度、2至8个对象、完整且等长的状态单元格、状态说明和阅读边界："
            f"{invalid_status_matrix_indexes}"
        )
    if invalid_status_matrix_anchors:
        depth_issues.append(f"状态矩阵指向不存在的 section id：{invalid_status_matrix_anchors}")
    if invalid_decision_table_indexes:
        depth_issues.append(
            "条件决策表需要2至8条完整的条件、结果、行动和语义色，并提供适用范围："
            f"{invalid_decision_table_indexes}"
        )
    if invalid_decision_table_anchors:
        depth_issues.append(f"条件决策表指向不存在的 section id：{invalid_decision_table_anchors}")
    if invalid_flow_indexes:
        depth_issues.append(
            "流程图至少需要两个有效步骤；步骤探索器需要3至7个含阶段名、标题和说明的步骤，"
            f"并提供阅读边界：{invalid_flow_indexes}"
        )
    if invalid_flow_stepper_anchors:
        depth_issues.append(f"步骤探索器指向不存在的 section id：{invalid_flow_stepper_anchors}")
    if invalid_timeline_indexes:
        depth_issues.append(
            "时间线至少需要两个完整节点；时间拖动器需要3至8个含时间、标题和说明的节点，"
            f"并提供阅读边界：{invalid_timeline_indexes}"
        )
    if invalid_timeline_scrubber_anchors:
        depth_issues.append(f"时间拖动器指向不存在的 section id：{invalid_timeline_scrubber_anchors}")
    if invalid_layer_stack_indexes:
        depth_issues.append(f"多层结构需要2至7层，每层含层级名、标题和说明，并提供阅读边界：{invalid_layer_stack_indexes}")
    if oversized_matrix_indexes:
        warnings.append(
            "矩阵表格过长，除非读者确实需要逐格查数，否则应改用分层、切换或拆分展示："
            f"{oversized_matrix_indexes}"
        )
    if unregistered_scenario_assets:
        depth_issues.append(f"证据情景卡引用了未进入证据图库的媒体：{unregistered_scenario_assets}")
    if bad_anchors:
        depth_issues.append(f"实验或案例指向不存在的 section id：{bad_anchors}")
    if unknown_claim_refs:
        depth_issues.append(f"实验或案例引用了不存在的研究 claim id：{unknown_claim_refs}")
    if invalid_media_indexes:
        depth_issues.append(f"原始媒体缺少 media_id、类型、URL 或段落锚点：{invalid_media_indexes}")
    if invalid_media_anchors:
        depth_issues.append(f"原始媒体指向不存在的 section id：{invalid_media_anchors}")
    if unregistered_media:
        blockers.append(f"原始媒体没有出现在抓取登记中：{unregistered_media}")
    if media_discovery_status == "failed":
        blockers.append(
            "动态网页媒体发现未完成："
            + (_text(media_discovery.get("reason")) or "未提供失败原因")
        )
    if duplicate_media_urls:
        depth_issues.append(f"原始媒体被重复使用：{duplicate_media_urls}")
    if foreign_media_without_guidance:
        blockers.append(
            "外语媒体必须提供自然中文图注和观看重点/读图提示："
            f"{foreign_media_without_guidance}"
        )
    if media_explanation_gaps:
        warnings.append(
            "部分正文媒体缺少解释任务或具体观看重点；新稿应说明媒体帮助读者理解什么："
            f"{media_explanation_gaps}"
        )
    if invalid_media_omission_indexes:
        blockers.append(
            "媒体省略记录必须包含已登记 media_id 和具体理由："
            f"{invalid_media_omission_indexes}"
        )
    if unregistered_media_omissions:
        blockers.append(f"媒体省略记录引用了未登记素材：{unregistered_media_omissions}")
    if duplicate_media_omission_ids:
        depth_issues.append(f"同一媒体被重复记录为省略：{duplicate_media_omission_ids}")
    if conflicting_media_decisions:
        blockers.append(f"同一视频不能同时采用和省略：{conflicting_media_decisions}")
    if unexplained_demo_video_ids:
        blockers.append(
            "原页的重要演示或首屏视频既未采用，也没有具体省略理由："
            f"{unexplained_demo_video_ids}"
        )
    if missing_metric_story_ids:
        depth_issues.append(f"高优先级指标主张缺少完整数字叙事：{missing_metric_story_ids}")
    if dense_number_story_sections:
        blockers.append(
            "同一章节不得连续展示多张数字大卡；请保留一张承担论证任务的卡，"
            f"其余设置 suppress_visual=true：{dense_number_story_sections}"
        )
    if mixed_main_visual_sections:
        blockers.append(
            "同一章节已有图表或关系组件时，不得再公开展示大数字卡；请把数字并入唯一主视觉，"
            f"并将对应 number_story 设置 suppress_visual=true：{mixed_main_visual_sections}"
        )
    if incomplete_high_metric_ids:
        depth_issues.append(f"高优先级数字叙事缺少单位、分母、范围、时间、对照或变化、边界或登记来源：{incomplete_high_metric_ids}")
    if invalid_number_story_anchors:
        depth_issues.append(f"数字叙事指向不存在的 section id：{invalid_number_story_anchors}")
    if unknown_number_story_claim_ids:
        depth_issues.append(f"数字叙事引用了不存在的研究 claim id：{sorted(unknown_number_story_claim_ids)}")
    if unregistered_number_story_assets:
        blockers.append(f"数字叙事引用了未登记媒体：{sorted(unregistered_number_story_assets)}")
    if unregistered_number_story_sources:
        blockers.append(f"数字叙事引用了未登记来源 URL：{unregistered_number_story_sources}")
    if invalid_gallery_items:
        depth_issues.append(f"证据图库包含未登记或结构无效的媒体：{invalid_gallery_items}")
    if duplicate_gallery_urls:
        depth_issues.append(f"证据图库存在重复 URL：{duplicate_gallery_urls}")
    if invalid_listening_cards:
        depth_issues.append(
            f"试听卡缺少标题、章节锚点、证据边界，或曲目缺少提示词与听感重点：{invalid_listening_cards}"
        )
    if invalid_listening_anchors:
        depth_issues.append(f"试听卡指向不存在的 section id：{invalid_listening_anchors}")
    if unregistered_listening_tracks:
        blockers.append(f"试听卡引用了未登记的音频：{unregistered_listening_tracks}")
    incomplete_noncritical = [
        story_id for story_id in incomplete_number_story_ids
        if story_id not in {
            _text(item.get("id"))
            for item in number_stories
            if _claim_ids(_list(item.get("claim_ids"))) & high_metric_ids
        }
    ]
    if incomplete_noncritical:
        warnings.append(f"不完整数字叙事已降级为普通正文：{incomplete_noncritical}")
    target = blockers if strict_editorial else warnings
    target.extend(depth_issues)


    return blockers, warnings, metrics
