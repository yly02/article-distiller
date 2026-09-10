"""文章完整性与连贯性质量门禁。

LLM 负责语义审校，本模块负责可重复验证的结构不变量：空内容、重复段落、
输出模式缺失，以及研究账本中高优先级主张是否被覆盖或明确舍弃。
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from language_quality import analyze_reader_voice, find_language_issues


OUTPUT_MODES = {"full"}
PLACEHOLDER_VALUES = {"内容", "正文", "待补充", "暂无", "省略", "todo", "tbd", "...", "…"}
UNKNOWN_NUMBER_VALUES = {"未知", "不详", "未提供", "材料未提供", "无明确对照", "unknown", "n/a", "na"}
META_NARRATION_RE = re.compile(
    r"(?:本文|原文|原博客|这篇文章|当前材料|本次材料|发布稿)(?:真正|反复|重点|还|又|只|足以|没有|未|把|要|将|的主线|说|称|提到|指出|显示|补充|提供|陈述|说明)?",
    flags=re.UNICODE,
)
PUBLIC_AUDIT_TONE_RE = re.compile(
    r"(?:本次读取|抓取状态|研究账本|运行日志|评判器|门禁结果|样本核对|样本量|独立评测|质量已经得到验证|不能据此推出)",
    flags=re.UNICODE,
)

SEMANTIC_ALIAS_PATTERNS = (
    (re.compile(r"(?:不会|不再|无需|不需要|没有)(?:额外)?(?:消耗|新增|增加|使用)"), "不增加"),
    (re.compile(r"(?:不会|不再|没有)(?:记录|包含|携带|保存)"), "不编码"),
    (re.compile(r"(?:个人|使用者|账户|账号|身份识别)信息"), "用户身份"),
    (re.compile(r"(?:几乎|基本)(?:没有|无)(?:明显)?影响|影响(?:很小|极小|不明显)"), "影响可忽略"),
    (re.compile(r"(?:没有|未)(?:观察到|发现)(?:统计)?显著(?:的)?(?:质量)?(?:下降|差异)"), "没有显著差异"),
    (re.compile(r"(?:不能|无法)(?:据此)?(?:证明|确认|判定)"), "不能确定"),
    (re.compile(r"(?:会|可以|能够)?(?:携带|形成|产生|留下)(?:新)?水印"), "会留下水印"),
    (re.compile(r"原文(?:称|表示|将|认为|提到|指出|说明)"), ""),
    (re.compile(r"发布方(?:称|表示|认为|提到|指出|说明)"), ""),
    (re.compile(r"solve\s*rate", flags=re.IGNORECASE), "成功率"),
    (re.compile(r"达到峰值"), "峰值"),
    (re.compile(r"用户(?:智能体|\s*agent\b)", flags=re.IGNORECASE), "useragent"),
    (re.compile(r"助手(?:智能体|\s*agent\b)", flags=re.IGNORECASE), "assistantagent"),
    (re.compile(r"(?:表示为|成为)"), "成为"),
    (re.compile(r"描述为"), ""),
    (re.compile(r"逐轮(?:进行|推进)"), "逐轮"),
    (re.compile(r"生成的集成成果"), "生成成果"),
)
SEMANTIC_GENERIC_NGRAMS = {
    "这个", "一种", "已经", "可以", "可能", "进行", "通过", "结果", "系统",
    "模型", "方法", "内容", "相关", "表示", "说明", "声称", "影响", "使用",
    "当前", "其中", "以及", "同时", "公开", "内部", "实际", "不同", "文本",
}
SEMANTIC_COMMON_LATIN = {
    "and", "are", "for", "from", "has", "have", "into", "not", "that", "the",
    "this", "through", "to", "with", "without",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _normalized_text(value: Any) -> str:
    text = _text(value).lower()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _char_count(*values: Any) -> int:
    return len(re.sub(r"\s+", "", "".join(_text(value) for value in values)))


def _is_placeholder(value: Any) -> bool:
    text = _text(value).lower()
    return text in PLACEHOLDER_VALUES or any(token in text for token in ("待补充", "稍后补充", "内容省略"))


def _duplicate_pairs(items: list[dict], title_key: str, body_key: str) -> list[dict]:
    duplicates = []
    for left in range(len(items)):
        for right in range(left + 1, len(items)):
            a = _normalized_text(items[left].get(title_key)) + _normalized_text(items[left].get(body_key))
            b = _normalized_text(items[right].get(title_key)) + _normalized_text(items[right].get(body_key))
            if not a or not b:
                continue
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= 0.88:
                duplicates.append({"first": left + 1, "second": right + 1, "similarity": round(ratio, 3)})
    return duplicates


def _claim_ids(items: Iterable[Any]) -> set[str]:
    result = set()
    for item in items:
        if isinstance(item, dict):
            claim_id = _text(item.get("id") or item.get("claim_id"))
        else:
            claim_id = _text(item)
        if claim_id:
            result.add(claim_id)
    return result


def _has_content(value: Any) -> bool:
    if isinstance(value, list):
        return any(_text(item) for item in value)
    return bool(_text(value))


def _known_number_context(value: Any) -> bool:
    text = _text(value)
    return bool(text) and text.casefold() not in UNKNOWN_NUMBER_VALUES


def _valid_experiment(item: dict) -> bool:
    required = ("id", "after_section_id", "question", "setup", "metric", "result", "limitations")
    return all(_has_content(item.get(key)) for key in required) and bool(_claim_ids(_list(item.get("claim_ids"))))


def _valid_case_story(item: dict) -> bool:
    beats = [
        beat for beat in _list(item.get("beats"))
        if isinstance(beat, dict) and _text(beat.get("label")) and _text(beat.get("text"))
    ]
    source_mode = _text(item.get("source_mode")).lower()
    return (
        all(_has_content(item.get(key)) for key in ("id", "after_section_id", "title", "setup", "outcome", "boundary"))
        and source_mode in {"reconstruction", "quoted"}
        and len(beats) >= 3
        and bool(_claim_ids(_list(item.get("claim_ids"))))
    )


def _valid_interactive_compare(item: dict) -> bool:
    if _text(item.get("type")).lower() != "interactive_compare":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    options = [x for x in _list(data.get("options")) if isinstance(x, dict) and _text(x.get("label"))]
    modes = [x for x in _list(data.get("modes")) if isinstance(x, dict) and _text(x.get("label"))]
    if len(options) < 2 or len(modes) < 2 or not _text(data.get("caption")):
        return False
    for mode in modes:
        selected_index = mode.get("selected_index")
        if (
            not isinstance(selected_index, int)
            or isinstance(selected_index, bool)
            or not 0 <= selected_index < len(options)
        ):
            return False
    return True


def _valid_strategy_tabs(item: dict) -> bool:
    if _text(item.get("type")).lower() != "strategy_tabs":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    strategies = [x for x in _list(data.get("strategies")) if isinstance(x, dict)]
    if not 2 <= len(strategies) <= 6 or not _text(data.get("boundary") or data.get("caption")):
        return False
    for strategy in strategies:
        if not all(_text(strategy.get(key)) for key in (
            "label", "target", "mechanism", "expected_effect", "open_questions"
        )):
            return False
        if _text(strategy.get("tone")).lower() not in {
            "primary", "baseline", "warning", "danger", "neutral"
        }:
            return False
    return True


def _valid_scenario_calculator(item: dict) -> bool:
    if _text(item.get("type")).lower() != "scenario_calculator":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    tabs = [x for x in _list(data.get("tabs")) if isinstance(x, dict) and _text(x.get("label"))]
    slider = data.get("slider") if isinstance(data.get("slider"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    source_asset_ids = _claim_ids(_list(data.get("source_asset_ids")))
    if len(tabs) < 2 or not source_asset_ids or not _text(data.get("caption")):
        return False
    if any(not [m for m in _list(tab.get("metrics")) if isinstance(m, dict) and _text(m.get("label")) and _has_content(m.get("value"))] for tab in tabs):
        return False
    try:
        minimum = float(slider.get("min"))
        maximum = float(slider.get("max"))
        step = float(slider.get("step"))
        value = float(slider.get("value"))
        float(result.get("base"))
    except (TypeError, ValueError):
        return False
    return maximum > minimum and step > 0 and minimum <= value <= maximum and bool(_text(result.get("label")))


def _valid_capacity_curve(item: dict) -> bool:
    if _text(item.get("type")).lower() != "capacity_curve":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    states = [x for x in _list(data.get("states")) if isinstance(x, dict)]
    caption = _text(data.get("caption"))
    if (
        not 3 <= len(states) <= 5
        or not _text(data.get("axis_label"))
        or not _text(data.get("result_label"))
        or "定性" not in caption
        or not any(word in caption for word in ("不是", "不代表", "随"))
    ):
        return False
    positions = []
    for state in states:
        if not all(_text(state.get(key)) for key in ("label", "result")):
            return False
        if _text(state.get("tone")).lower() not in {"primary", "baseline", "warning", "danger", "neutral"}:
            return False
        try:
            position = float(state.get("position"))
        except (TypeError, ValueError):
            return False
        if not 0 <= position <= 100:
            return False
        positions.append(position)
    return positions == sorted(positions) and len(set(positions)) == len(positions)


def _valid_cost_ledger(item: dict) -> bool:
    if _text(item.get("type")).lower() != "cost_ledger":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    cost_labels = [_text(x) for x in _list(data.get("cost_labels")) if _text(x)]
    scenarios = [x for x in _list(data.get("scenarios")) if isinstance(x, dict)]
    if not 1 <= len(cost_labels) <= 4 or len(set(cost_labels)) != len(cost_labels):
        return False
    if not 2 <= len(scenarios) <= 6 or not _text(data.get("boundary")):
        return False
    scenario_ids = []
    allowed_costs = set(cost_labels)
    for scenario in scenarios:
        scenario_id = _text(scenario.get("id"))
        if not scenario_id or not all(_text(scenario.get(key)) for key in ("label", "verdict", "explanation")):
            return False
        scenario_ids.append(scenario_id)
        included = {_text(x) for x in _list(scenario.get("included")) if _text(x)}
        if not included.issubset(allowed_costs):
            return False
    return len(set(scenario_ids)) == len(scenario_ids)


def _valid_metric_bars(item: dict) -> bool:
    if _text(item.get("type")).lower() != "metric_bars":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    groups = [x for x in _list(data.get("groups")) if isinstance(x, dict)]
    if (
        len(groups) < 2
        or not _text(data.get("primary_label"))
        or not _text(data.get("baseline_label"))
        or not _text(data.get("boundary"))
    ):
        return False
    for group in groups:
        if not all(_text(group.get(key)) for key in ("id", "label", "question", "metric")):
            return False
        if _text(group.get("better")).lower() not in {"higher", "lower"}:
            return False
        rows = [x for x in _list(group.get("rows")) if isinstance(x, dict)]
        if len(rows) < 2:
            return False
        for row in rows:
            if not all(_text(row.get(key)) for key in ("label", "primary_display", "baseline_display", "ratio")):
                return False
            try:
                primary_value = float(row.get("primary_value"))
                baseline_value = float(row.get("baseline_value"))
            except (TypeError, ValueError):
                return False
            if primary_value <= 0 or baseline_value <= 0:
                return False
    return True


def _valid_rank_bars(item: dict) -> bool:
    if _text(item.get("type")).lower() != "rank_bars":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    groups = [x for x in _list(data.get("groups")) if isinstance(x, dict)]
    if not 1 <= len(groups) <= 4 or not _text(data.get("boundary")):
        return False
    for group in groups:
        if not all(_text(group.get(key)) for key in ("id", "label", "question", "unit")):
            return False
        direction = _text(group.get("direction")).lower()
        if direction not in {"positive", "negative"}:
            return False
        if _text(group.get("tone")).lower() not in {"primary", "baseline", "warning", "danger"}:
            return False
        rows = [x for x in _list(group.get("rows")) if isinstance(x, dict)]
        if not 2 <= len(rows) <= 18:
            return False
        magnitudes = []
        for row in rows:
            if not all(_text(row.get(key)) for key in ("label", "display")):
                return False
            try:
                value = float(row.get("value"))
            except (TypeError, ValueError):
                return False
            if (direction == "positive" and value < 0) or (direction == "negative" and value > 0):
                return False
            magnitudes.append(abs(value))
        if not any(value > 0 for value in magnitudes):
            return False
        if any(left < right for left, right in zip(magnitudes, magnitudes[1:])):
            return False
    return True


def _valid_funnel_flow(item: dict) -> bool:
    if _text(item.get("type")).lower() != "funnel_flow":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    steps = [x for x in _list(data.get("steps")) if isinstance(x, dict)]
    if not 2 <= len(steps) <= 5 or not _text(data.get("entry_label")) or not _text(data.get("caption")):
        return False
    widths = []
    for step in steps:
        if not _text(step.get("label") or step.get("title")) or not _text(step.get("description") or step.get("text")):
            return False
        if step.get("width") not in (None, ""):
            try:
                width = float(step.get("width"))
            except (TypeError, ValueError):
                return False
            if not 48 <= width <= 100:
                return False
            widths.append(width)
    if widths and (len(widths) != len(steps) or any(left <= right for left, right in zip(widths, widths[1:]))):
        return False
    return True


def _valid_delta_table(item: dict) -> bool:
    if _text(item.get("type")).lower() != "delta_table":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    rows = [x for x in _list(data.get("rows")) if isinstance(x, dict)]
    if (
        not 2 <= len(rows) <= 8
        or not _text(data.get("baseline_label"))
        or not _text(data.get("current_label"))
        or not _text(data.get("boundary"))
    ):
        return False
    allowed_tones = {"primary", "baseline", "warning", "danger", "neutral"}
    for row in rows:
        if not all(_text(row.get(key)) for key in ("label", "baseline", "current", "change", "direction", "tone")):
            return False
        if _text(row.get("direction")).lower() not in {"up", "down", "flat"}:
            return False
        if _text(row.get("tone")).lower() not in allowed_tones:
            return False
    return True


def _valid_status_matrix(item: dict) -> bool:
    if _text(item.get("type")).lower() != "status_matrix":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    columns = [_text(x) for x in _list(data.get("columns")) if _text(x)]
    rows = [x for x in _list(data.get("rows")) if isinstance(x, dict)]
    if (
        not 2 <= len(columns) <= 6
        or not 2 <= len(rows) <= 8
        or not _text(data.get("caption"))
        or not _text(data.get("boundary"))
    ):
        return False
    allowed_tones = {"primary", "baseline", "warning", "danger", "neutral"}
    for row in rows:
        cells = [x for x in _list(row.get("cells")) if isinstance(x, dict)]
        if not _text(row.get("label")) or len(cells) != len(columns):
            return False
        if any(
            not _text(cell.get("value"))
            or _text(cell.get("tone")).lower() not in allowed_tones
            for cell in cells
        ):
            return False
    return True


def _valid_decision_table(item: dict) -> bool:
    if _text(item.get("type")).lower() != "decision_table":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    rows = [x for x in _list(data.get("rows")) if isinstance(x, dict)]
    if not 2 <= len(rows) <= 8 or not _text(data.get("boundary")):
        return False
    allowed_tones = {"primary", "baseline", "warning", "danger", "neutral"}
    return all(
        all(_text(row.get(key)) for key in ("condition", "result", "action", "tone"))
        and _text(row.get("tone")).lower() in allowed_tones
        for row in rows
    )


def _valid_flow_visual(item: dict) -> bool:
    if _text(item.get("type")).lower() != "flow":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    steps = _list(data.get("steps"))
    if len(steps) < 2:
        return False
    presentation = _text(data.get("presentation")).lower()
    if presentation == "stepper":
        if not 3 <= len(steps) <= 7 or not _text(data.get("caption")):
            return False
        return all(
            isinstance(step, dict)
            and _text(step.get("label"))
            and _text(step.get("title"))
            and _text(step.get("description"))
            for step in steps
        )
    if presentation not in {"", "static"}:
        return False
    for step in steps:
        if isinstance(step, dict):
            if not (_has_content(step.get("title") or step.get("label")) or _has_content(step.get("description") or step.get("text"))):
                return False
        elif not _has_content(step):
            return False
    return True


def _valid_timeline_visual(item: dict) -> bool:
    if _text(item.get("type")).lower() != "timeline":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    presentation = _text(data.get("presentation")).lower()
    events = [x for x in _list(data.get("events")) if isinstance(x, dict)]
    if presentation in {"", "static"}:
        return len(events) >= 2 and all(
            _text(event.get("time")) and _text(event.get("title") or event.get("event"))
            for event in events
        )
    if presentation != "scrubber" or not 3 <= len(events) <= 8 or not _text(data.get("caption")):
        return False
    return all(
        _text(event.get("time"))
        and _text(event.get("title") or event.get("event"))
        and _text(event.get("description"))
        for event in events
    )


def _valid_layer_stack(item: dict) -> bool:
    if _text(item.get("type")).lower() != "layer_stack":
        return True
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    layers = [x for x in _list(data.get("layers")) if isinstance(x, dict)]
    if not 2 <= len(layers) <= 7 or not _text(data.get("caption")):
        return False
    return all(
        _text(layer.get("label"))
        and _text(layer.get("title"))
        and _text(layer.get("description"))
        for layer in layers
    )



__all__ = [name for name in list(globals()) if not name.startswith("__")]
