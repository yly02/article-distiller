"""按内容关系选择的交互组件渲染。"""
from .text import _esc, _visual_tone

def _render_visual(v: dict) -> str:
    t = v.get("type", "")
    title = _esc(v.get("title") or "")
    data = v.get("data") or {}
    parts = []
    if title:
        parts.append(f'<p class="visual-title">{title}</p>')

    if t == "compare_table":
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        column_roles = data.get("column_roles", [])
        layout = str(data.get("layout") or "stacked").strip().lower()

        def _compare_cells(row):
            if isinstance(row, dict):
                cells = row.get("cells")
                if isinstance(cells, list):
                    return cells
                if row.get("label") is not None:
                    return [row.get("label"), *list(row.get("values") or [])]
                return []
            if isinstance(row, (list, tuple)):
                return list(row)
            return []

        if layout == "matrix":
            parts.append('<div class="cmp-scroll"><table class="cmp-table"><thead><tr>')
            for index, header in enumerate(headers):
                tone = _visual_tone(column_roles[index] if index < len(column_roles) else "")
                tone_class = f' class="cmp-tone-{tone}"' if tone else ""
                parts.append(f'<th{tone_class}>{_esc(header)}</th>')
            parts.append('</tr></thead><tbody>')
            for row in rows:
                cells = _compare_cells(row)
                if not cells:
                    continue
                parts.append('<tr>')
                for index, cell in enumerate(cells):
                    tone = _visual_tone(column_roles[index] if index < len(column_roles) else "")
                    tone_class = f' class="cmp-tone-{tone}"' if tone else ""
                    parts.append(f'<td{tone_class}>{_esc(cell)}</td>')
                parts.append('</tr>')
            parts.append('</tbody></table></div>')
        else:
            layout_class = "paired" if layout == "paired" else "stacked"
            parts.append(f'<div class="comparison-list {layout_class}">')
            for row in rows:
                cells = _compare_cells(row)
                if not cells:
                    continue
                topic = cells[0]
                parts.append('<section class="comparison-row">')
                parts.append(f'<div class="comparison-topic">{_esc(topic)}</div>')
                parts.append('<dl class="comparison-pairs">')
                for index, cell in enumerate(cells[1:], 1):
                    label = headers[index] if index < len(headers) else f"对比项 {index}"
                    tone = _visual_tone(column_roles[index] if index < len(column_roles) else "")
                    tone_class = f" cmp-tone-{tone}" if tone else ""
                    parts.append(
                        f'<div class="comparison-pair{tone_class}">'
                        f'<dt>{_esc(label)}</dt><dd>{_esc(cell)}</dd>'
                        '</div>'
                    )
                parts.append('</dl></section>')
            parts.append("</div>")

    elif t == "delta_table":
        rows = [x for x in (data.get("rows") or []) if isinstance(x, dict)]
        baseline_label = str(data.get("baseline_label") or "调整前").strip()
        current_label = str(data.get("current_label") or "调整后").strip()
        boundary = str(data.get("boundary") or "").strip()
        if rows:
            parts.append('<div class="delta-table">')
            parts.append(
                f'<div class="delta-head"><span>指标</span><span>{_esc(baseline_label)} → {_esc(current_label)}</span><span>变化</span></div>'
            )
            direction_symbols = {"up": "↑", "down": "↓", "flat": "→"}
            for row in rows:
                direction = str(row.get("direction") or "flat").strip().lower()
                tone = _visual_tone(row.get("tone"))
                tone_class = f" tone-{tone}" if tone else ""
                parts.append('<div class="delta-row">')
                parts.append(f'<div class="delta-label">{_esc(row.get("label") or "指标")}</div>')
                parts.append('<div class="delta-values">')
                parts.append(
                    f'<div class="delta-value"><span class="delta-value-label">{_esc(baseline_label)}</span>'
                    f'<strong>{_esc(row.get("baseline") or "")}</strong></div>'
                )
                parts.append('<span class="delta-arrow" aria-hidden="true">→</span>')
                parts.append(
                    f'<div class="delta-value current"><span class="delta-value-label">{_esc(current_label)}</span>'
                    f'<strong>{_esc(row.get("current") or "")}</strong></div></div>'
                )
                parts.append(
                    f'<div class="delta-change{tone_class}"><span class="delta-direction" aria-hidden="true">'
                    f'{direction_symbols.get(direction, "→")}</span>{_esc(row.get("change") or "")}</div></div>'
                )
            if boundary:
                parts.append(f'<div class="delta-boundary"><strong>怎么读：</strong>{_esc(boundary)}</div>')
            parts.append('</div>')

    elif t == "status_matrix":
        columns = [str(x).strip() for x in (data.get("columns") or []) if str(x).strip()]
        rows = [x for x in (data.get("rows") or []) if isinstance(x, dict)]
        caption = str(data.get("caption") or "").strip()
        boundary = str(data.get("boundary") or "").strip()
        if columns and rows:
            parts.append('<div class="status-matrix-scroll"><table class="status-matrix"><thead><tr><th>对象</th>')
            parts.extend(f'<th>{_esc(column)}</th>' for column in columns)
            parts.append('</tr></thead><tbody>')
            for row in rows:
                parts.append(f'<tr><td>{_esc(row.get("label") or "对象")}</td>')
                for cell in (row.get("cells") or []):
                    if not isinstance(cell, dict):
                        continue
                    tone = _visual_tone(cell.get("tone"))
                    tone_class = f' class="tone-{tone}"' if tone else ""
                    parts.append(f'<td{tone_class}>{_esc(cell.get("value") or "")}</td>')
                parts.append('</tr>')
            parts.append('</tbody></table></div>')
            if caption:
                parts.append(f'<div class="status-caption">{_esc(caption)}</div>')
            if boundary:
                parts.append(f'<div class="status-boundary"><strong>怎么读：</strong>{_esc(boundary)}</div>')

    elif t == "decision_table":
        rows = [x for x in (data.get("rows") or []) if isinstance(x, dict)]
        boundary = str(data.get("boundary") or "").strip()
        if rows:
            parts.append('<div class="decision-table">')
            parts.append('<div class="decision-head"><span>条件</span><span>结果</span><span>可以怎么做</span></div>')
            for row in rows:
                tone = _visual_tone(row.get("tone"))
                tone_class = f" tone-{tone}" if tone else ""
                parts.append(f'<div class="decision-row{tone_class}">')
                parts.append(f'<div class="decision-cell condition">{_esc(row.get("condition") or "")}</div>')
                parts.append(f'<div class="decision-cell result">{_esc(row.get("result") or "")}</div>')
                parts.append(f'<div class="decision-cell action">{_esc(row.get("action") or "")}</div></div>')
            if boundary:
                parts.append(f'<div class="decision-boundary"><strong>适用范围：</strong>{_esc(boundary)}</div>')
            parts.append('</div>')

    elif t == "metric_bars":
        groups = [x for x in (data.get("groups") or []) if isinstance(x, dict)]
        primary_label = str(data.get("primary_label") or "方案 A")
        baseline_label = str(data.get("baseline_label") or "方案 B")
        normalization_note = str(
            data.get("normalization_note")
            or "条长只在同一模型、同一指标内归一化；标注数字保留原值。"
        )
        boundary = str(data.get("boundary") or "")
        if groups:
            parts.append('<div class="metric-bars" data-metric-bars>')
            parts.append('<div class="mb-tabs" role="group" aria-label="切换比较指标">')
            for index, group in enumerate(groups):
                active = " active" if index == 0 else ""
                pressed = "true" if index == 0 else "false"
                parts.append(
                    f'<button type="button" class="mb-tab{active}" data-metric-tab="{index}" '
                    f'aria-pressed="{pressed}">{_esc(group.get("label") or f"指标 {index + 1}")}</button>'
                )
            parts.append('</div>')
            for index, group in enumerate(groups):
                parts.append(f'<section class="mb-panel" data-metric-panel="{index}">')
                parts.append(f'<p class="mb-question">{_esc(group.get("question") or "比较结果")}</p>')
                if group.get("metric"):
                    parts.append(f'<div class="mb-metric">指标：{_esc(group.get("metric"))}</div>')
                rows = [x for x in (group.get("rows") or []) if isinstance(x, dict)]
                for row in rows:
                    try:
                        primary_value = float(row.get("primary_value"))
                        baseline_value = float(row.get("baseline_value"))
                    except (TypeError, ValueError):
                        continue
                    maximum = max(primary_value, baseline_value)
                    if maximum <= 0:
                        continue
                    primary_width = max(3.0, primary_value / maximum * 100)
                    baseline_width = max(3.0, baseline_value / maximum * 100)
                    parts.append('<div class="mb-model">')
                    parts.append(f'<div class="mb-model-name">{_esc(row.get("label") or "比较对象")}</div>')
                    parts.append('<div class="mb-pair">')
                    parts.append(
                        '<div class="mb-line primary">'
                        f'<span class="mb-series">{_esc(primary_label)}</span>'
                        f'<span class="mb-track"><span class="mb-fill" style="--bar-width:{primary_width:.2f}%"></span></span>'
                        f'<span class="mb-value">{_esc(row.get("primary_display") or f"{primary_value:g}")}</span>'
                        '</div>'
                    )
                    parts.append(
                        '<div class="mb-line baseline">'
                        f'<span class="mb-series">{_esc(baseline_label)}</span>'
                        f'<span class="mb-track"><span class="mb-fill" style="--bar-width:{baseline_width:.2f}%"></span></span>'
                        f'<span class="mb-value">{_esc(row.get("baseline_display") or f"{baseline_value:g}")}</span>'
                        '</div></div>'
                    )
                    parts.append(f'<div class="mb-ratio">{_esc(row.get("ratio") or "")}</div></div>')
                parts.append('</section>')
            parts.append(f'<div class="mb-note">{_esc(normalization_note)}</div>')
            if boundary:
                parts.append(f'<div class="mb-boundary"><strong>怎么读：</strong>{_esc(boundary)}</div>')
            parts.append('</div>')

    elif t == "rank_bars":
        groups = [x for x in (data.get("groups") or []) if isinstance(x, dict)]
        caption = str(data.get("caption") or "").strip()
        boundary = str(data.get("boundary") or "").strip()
        if groups:
            parts.append('<div class="rank-bars" data-rank-bars>')
            if len(groups) > 1:
                parts.append('<div class="rb-tabs" role="group" aria-label="切换参数组">')
                for index, group in enumerate(groups):
                    active = " active" if index == 0 else ""
                    pressed = "true" if index == 0 else "false"
                    parts.append(
                        f'<button type="button" class="rb-tab{active}" data-rank-tab="{index}" '
                        f'aria-pressed="{pressed}">{_esc(group.get("label") or f"分组 {index + 1}")}</button>'
                    )
                parts.append('</div>')
            for index, group in enumerate(groups):
                tone = _visual_tone(group.get("tone")) or "primary"
                hidden = "" if index == 0 else " hidden"
                rows = [x for x in (group.get("rows") or []) if isinstance(x, dict)]
                numeric_values = []
                for row in rows:
                    try:
                        numeric_values.append(abs(float(row.get("value"))))
                    except (TypeError, ValueError):
                        numeric_values.append(0.0)
                maximum = max(numeric_values, default=0.0)
                parts.append(
                    f'<section class="rb-panel tone-{tone}" data-rank-panel="{index}"{hidden}>'
                )
                question = str(group.get("question") or "").strip()
                if question:
                    parts.append(f'<p class="rb-question">{_esc(question)}</p>')
                for row, numeric_value in zip(rows, numeric_values):
                    width = numeric_value / maximum * 100 if maximum > 0 else 0
                    display = row.get("display")
                    if display in (None, ""):
                        display = f'{row.get("value", "")}{group.get("unit") or ""}'
                    parts.append('<div class="rb-row">')
                    parts.append(f'<div class="rb-label">{_esc(row.get("label") or "比较对象")}</div>')
                    parts.append(
                        '<div class="rb-track" aria-hidden="true">'
                        f'<span class="rb-fill" style="--bar-width:{width:.2f}%"></span></div>'
                    )
                    parts.append(f'<div class="rb-value">{_esc(display)}</div>')
                    note = str(row.get("note") or "").strip()
                    if note:
                        parts.append(f'<div class="rb-note">{_esc(note)}</div>')
                    parts.append('</div>')
                parts.append('</section>')
            if caption:
                parts.append(f'<div class="rb-caption">{_esc(caption)}</div>')
            if boundary:
                parts.append(f'<div class="rb-boundary"><strong>怎么读：</strong>{_esc(boundary)}</div>')
            parts.append('</div>')

    elif t == "funnel_flow":
        steps = [x for x in (data.get("steps") or []) if isinstance(x, dict)]
        entry_label = str(data.get("entry_label") or "进入流程的全部对象").strip()
        caption = str(data.get("caption") or "").strip()
        if steps:
            parts.append('<div class="funnel-flow">')
            parts.append(f'<div class="ff-entry">{_esc(entry_label)}</div>')
            for index, step in enumerate(steps):
                try:
                    requested_width = float(step.get("width"))
                except (TypeError, ValueError):
                    requested_width = 100 - index * 18
                width = max(48.0, min(100.0, requested_width))
                parts.append('<div class="ff-arrow">\u2193</div>')
                parts.append(f'<div class="ff-stage" style="--funnel-width:{width:.1f}%">')
                parts.append(f'<span class="ff-label">{_esc(step.get("label") or step.get("title") or f"第 {index + 1} 关")}</span>')
                description = str(step.get("description") or step.get("text") or "").strip()
                if description:
                    parts.append(f'<span class="ff-description">{_esc(description)}</span>')
                parts.append('</div>')
                exit_label = str(step.get("exit_label") or "").strip()
                if exit_label:
                    parts.append(f'<div class="ff-exit">这一关会拿掉：{_esc(exit_label)}</div>')
            if caption:
                parts.append(f'<div class="ff-caption">{_esc(caption)}</div>')
            parts.append('</div>')

    elif t == "flow":
        steps = data.get("steps", [])
        presentation = str(data.get("presentation") or "static").strip().lower()
        if presentation == "stepper" and all(isinstance(step, dict) for step in steps):
            caption = str(data.get("caption") or "").strip()
            parts.append('<div class="flow-stepper" data-flow-stepper>')
            parts.append('<div class="fs-nav" role="group" aria-label="选择流程阶段">')
            for index, step in enumerate(steps):
                active = " active" if index == 0 else ""
                pressed = "true" if index == 0 else "false"
                label = str(step.get("label") or step.get("title") or f"第 {index + 1} 步").strip()
                parts.append(
                    f'<button type="button" class="fs-tab{active}" data-flow-step="{index}" '
                    f'aria-pressed="{pressed}">{index + 1}. {_esc(label)}</button>'
                )
            parts.append('</div>')
            for index, step in enumerate(steps):
                active = " active" if index == 0 else ""
                label = str(step.get("label") or f"第 {index + 1} 步").strip()
                step_title = str(step.get("title") or label).strip()
                description = str(step.get("description") or step.get("text") or "").strip()
                result = str(step.get("result") or "").strip()
                parts.append(f'<section class="fs-panel{active}" data-flow-panel="{index}">')
                parts.append(f'<div class="fs-kicker">第 {index + 1} / {len(steps)} 步 · {_esc(label)}</div>')
                parts.append(f'<div class="fs-title">{_esc(step_title)}</div>')
                parts.append(f'<div class="fs-description">{_esc(description)}</div>')
                if result:
                    parts.append(f'<div class="fs-result"><strong>结果：</strong>{_esc(result)}</div>')
                parts.append('</section>')
            parts.append('<div class="fs-controls">')
            parts.append('<button type="button" class="fs-control" data-flow-prev aria-label="上一步" title="上一步" disabled>←</button>')
            parts.append('<button type="button" class="fs-control" data-flow-next aria-label="下一步" title="下一步">→</button>')
            parts.append('</div>')
            if caption:
                parts.append(f'<div class="fs-caption">{_esc(caption)}</div>')
            parts.append('</div>')
        else:
            parts.append('<div class="flow">')
            for i, s in enumerate(steps, 1):
                if isinstance(s, dict):
                    step_title = str(s.get("title") or s.get("label") or "").strip()
                    step_description = str(s.get("description") or s.get("text") or "").strip()
                    if step_title and step_description:
                        step_html = (
                            '<span class="flow-copy">'
                            f'<span class="flow-title">{_esc(step_title)}</span>'
                            f'<span class="flow-description">{_esc(step_description)}</span>'
                            '</span>'
                        )
                    else:
                        step_html = f'<span class="flow-copy">{_esc(step_title or step_description)}</span>'
                else:
                    step_html = f'<span class="flow-copy">{_esc(s)}</span>'
                parts.append(
                    f'<div class="flow-step"><span class="flow-num">{i}</span>'
                    f'{step_html}</div>'
                )
                if i < len(steps):
                    parts.append('<div class="flow-arrow">\u2193</div>')
            parts.append("</div>")

    elif t == "strategy_tabs":
        strategies = [x for x in (data.get("strategies") or []) if isinstance(x, dict)]
        instruction = str(data.get("instruction") or "切换方案，查看它分别改变哪一层问题。").strip()
        boundary = str(data.get("boundary") or data.get("caption") or "").strip()
        if strategies:
            parts.append('<div class="strategy-tabs" data-strategy-tabs>')
            if instruction:
                parts.append(f'<div class="st-instruction">{_esc(instruction)}</div>')
            parts.append('<div class="st-nav" role="tablist" aria-label="切换策略方案">')
            for index, strategy in enumerate(strategies):
                tone = _visual_tone(strategy.get("tone")) or "primary"
                active = " active" if index == 0 else ""
                selected = "true" if index == 0 else "false"
                parts.append(
                    f'<button type="button" role="tab" class="st-tab tone-{tone}{active}" '
                    f'data-strategy-tab="{index}" data-step="{index + 1:02d}" '
                    f'aria-selected="{selected}">{_esc(strategy.get("label") or f"方案 {index + 1}")}</button>'
                )
            parts.append('</div>')
            for index, strategy in enumerate(strategies):
                tone = _visual_tone(strategy.get("tone")) or "primary"
                active = " active" if index == 0 else ""
                parts.append(
                    f'<section role="tabpanel" class="st-panel tone-{tone}{active}" data-strategy-panel="{index}">'
                )
                parts.append('<div class="st-panel-head">')
                parts.append(f'<div class="st-panel-title">{_esc(strategy.get("label") or f"方案 {index + 1}")}</div>')
                parts.append(f'<div class="st-panel-target">作用对象 · {_esc(strategy.get("target") or "")}</div></div>')
                parts.append('<div class="st-grid">')
                parts.append('<div class="st-item"><span class="st-label">它怎样起作用</span>')
                parts.append(f'<div class="st-value">{_esc(strategy.get("mechanism") or "")}</div></div>')
                parts.append('<div class="st-item"><span class="st-label">希望带来什么变化</span>')
                parts.append(f'<div class="st-value">{_esc(strategy.get("expected_effect") or "")}</div></div>')
                parts.append('<div class="st-item open"><span class="st-label">真正落地还缺什么</span>')
                parts.append(f'<div class="st-value">{_esc(strategy.get("open_questions") or "")}</div></div>')
                parts.append('</div></section>')
            if boundary:
                parts.append(f'<div class="st-boundary"><strong>阅读边界：</strong>{_esc(boundary)}</div>')
            parts.append('</div>')

    elif t == "layer_stack":
        layers = [x for x in (data.get("layers") or []) if isinstance(x, dict)]
        caption = str(data.get("caption") or "").strip()
        if layers:
            parts.append('<div class="layer-stack">')
            for index, layer in enumerate(layers, 1):
                opened = " open" if index == 1 else ""
                label = str(layer.get("label") or f"第 {index} 层").strip()
                layer_title = str(layer.get("title") or "").strip()
                description = str(layer.get("description") or "").strip()
                points = [str(x).strip() for x in (layer.get("items") or []) if str(x).strip()]
                parts.append(f'<details class="layer-item"{opened}>')
                parts.append(
                    '<summary>'
                    f'<span class="layer-index">{index:02d}</span>'
                    '<span class="layer-heading">'
                    f'<span class="layer-label">{_esc(label)}</span>'
                    f'<span class="layer-title">{_esc(layer_title)}</span>'
                    '</span><span class="layer-toggle" aria-hidden="true"></span>'
                    '</summary>'
                )
                parts.append(f'<div class="layer-body">{_esc(description)}')
                if points:
                    parts.append('<ul class="layer-points">')
                    parts.extend(f'<li>{_esc(point)}</li>' for point in points)
                    parts.append('</ul>')
                parts.append('</div></details>')
            parts.append('</div>')
            if caption:
                parts.append(f'<div class="layer-caption"><strong>怎么读：</strong>{_esc(caption)}</div>')

    elif t == "stat":
        items = data.get("items", [])
        unit = _esc(data.get("unit") or "")
        parts.append('<div class="stat-grid">')
        for it in items:
            tone = _visual_tone(it.get("tone"))
            tone_class = f" tone-{tone}" if tone else ""
            parts.append(
                f'<div class="stat-card{tone_class}"><div class="stat-val">'
                f'{_esc(it.get("value", ""))}{unit}</div>'
                f'<div class="stat-label">{_esc(it.get("label", ""))}</div></div>'
            )
        parts.append("</div>")

    elif t == "timeline":
        events = [event for event in (data.get("events") or []) if isinstance(event, dict)]
        presentation = str(data.get("presentation") or "static").strip().lower()
        if presentation == "scrubber" and events:
            caption = str(data.get("caption") or "").strip()
            first = events[0]
            first_title = str(first.get("title") or first.get("event") or "").strip()
            parts.append('<div class="timeline-scrubber" data-timeline-scrubber>')
            parts.append('<div class="ts-stage" aria-live="polite">')
            parts.append(f'<div class="ts-time" data-timeline-time>{_esc(first.get("time") or "")}</div>')
            parts.append(f'<div class="ts-title" data-timeline-title>{_esc(first_title)}</div>')
            parts.append(f'<div class="ts-description" data-timeline-description>{_esc(first.get("description") or "")}</div></div>')
            parts.append(
                f'<input class="ts-range" type="range" min="0" max="{len(events) - 1}" step="1" value="0" '
                'data-timeline-input aria-label="拖动查看时间节点">'
            )
            parts.append('<div class="ts-ticks" aria-hidden="true">')
            parts.extend(f'<span>{_esc(event.get("time") or "")}</span>' for event in events)
            parts.append('</div><ol class="ts-fallback">')
            for event in events:
                event_title = str(event.get("title") or event.get("event") or "").strip()
                parts.append(f'<li><strong>{_esc(event.get("time") or "")}</strong> · {_esc(event_title)}</li>')
            parts.append('</ol>')
            for index, event in enumerate(events):
                event_title = str(event.get("title") or event.get("event") or "").strip()
                parts.append(
                    f'<span hidden data-timeline-event="{index}" data-time="{_esc(event.get("time") or "")}" '
                    f'data-title="{_esc(event_title)}" data-description="{_esc(event.get("description") or "")}"></span>'
                )
            if caption:
                parts.append(f'<div class="ts-caption">{_esc(caption)}</div>')
            parts.append('</div>')
        else:
            parts.append('<div class="timeline">')
            for e in events:
                event_title = str(e.get("title") or e.get("event") or "").strip()
                description = str(e.get("description") or "").strip()
                body_parts = []
                if event_title:
                    body_parts.append(f'<span class="tl-title">{_esc(event_title)}</span>')
                if description:
                    body_parts.append(f'<span class="tl-description">{_esc(description)}</span>')
                parts.append(
                    f'<div class="tl-event"><div class="tl-time">{_esc(e.get("time", ""))}</div>'
                    f'<div class="tl-body">{"".join(body_parts)}</div></div>'
                )
            parts.append("</div>")

    elif t == "interactive_compare":
        instruction = data.get("instruction") or "切换模式，观察同一组候选怎样得到不同结果。"
        prompt = data.get("prompt") or ""
        options = [x for x in (data.get("options") or []) if isinstance(x, dict)]
        modes = [x for x in (data.get("modes") or []) if isinstance(x, dict)]
        takeaway = data.get("takeaway") or ""
        caption = data.get("caption") or "机制示意，不代表真实概率、模型输出或检测结果。"
        if options and modes:
            parts.append('<div class="interactive-compare" data-interactive-compare>')
            parts.append(f'<div class="ic-instruction">{_esc(instruction)}</div>')
            parts.append('<div class="ic-toggle" role="group" aria-label="切换比较模式">')
            for index, mode in enumerate(modes):
                active = " active" if index == 0 else ""
                pressed = "true" if index == 0 else "false"
                parts.append(
                    f'<button type="button" class="ic-mode{active}" data-interactive-mode="{index}" '
                    f'aria-pressed="{pressed}">{_esc(mode.get("label") or f"模式 {index + 1}")}</button>'
                )
            parts.append('</div>')
            if prompt:
                parts.append(f'<div class="ic-prompt">{_esc(prompt)}</div>')
            for index, mode in enumerate(modes):
                hidden = "" if index == 0 else " hidden"
                selected_index = mode.get("selected_index")
                if not isinstance(selected_index, int) or isinstance(selected_index, bool):
                    selected_index = -1
                parts.append(f'<div class="ic-state" data-interactive-state="{index}"{hidden}>')
                parts.append('<div class="ic-state-meta">')
                parts.append(
                    f'<span class="ic-state-label">{_esc(mode.get("result_label") or "本次选择")}</span>'
                )
                if mode.get("signal"):
                    parts.append(f'<span class="ic-state-signal">{_esc(mode.get("signal"))}</span>')
                parts.append('</div><div class="ic-options">')
                for option_index, option in enumerate(options):
                    selected = " selected" if option_index == selected_index else ""
                    parts.append(f'<div class="ic-option{selected}">')
                    parts.append(f'<div class="ic-option-name">{_esc(option.get("label") or "候选")}</div>')
                    if option.get("note"):
                        parts.append(f'<div class="ic-option-note">{_esc(option.get("note"))}</div>')
                    parts.append('</div>')
                parts.append('</div>')
                if mode.get("note"):
                    parts.append(f'<div class="ic-state-note">{_esc(mode.get("note"))}</div>')
                parts.append('</div>')
            if takeaway:
                parts.append(f'<div class="ic-takeaway">{_esc(takeaway)}</div>')
            parts.append(f'<div class="ic-caption">{_esc(caption)}</div></div>')

    elif t == "scenario_calculator":
        instruction = data.get("instruction") or "切换对象并调整假设，观察结果怎样变化。"
        tabs = [x for x in (data.get("tabs") or []) if isinstance(x, dict)]
        slider = data.get("slider") if isinstance(data.get("slider"), dict) else {}
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        formula_note = data.get("formula_note") or ""
        caption = data.get("caption") or "交互中的可调数值是情景假设，不是来源数据。"
        try:
            slider_min = float(slider.get("min", 0))
            slider_max = float(slider.get("max", 10))
            slider_step = float(slider.get("step", 1))
            slider_value = float(slider.get("value", slider_min))
            result_base = float(result.get("base"))
        except (TypeError, ValueError):
            tabs = []
        else:
            if slider_max <= slider_min or slider_step <= 0:
                tabs = []
            slider_value = min(max(slider_value, slider_min), slider_max)
        if tabs:
            decimals = result.get("decimals", 2)
            if not isinstance(decimals, int) or isinstance(decimals, bool):
                decimals = 2
            decimals = min(max(decimals, 0), 4)
            prefix = str(result.get("prefix") or "")
            initial_result = result_base - slider_value
            slider_prefix = str(slider.get("prefix") or "")
            slider_suffix = str(slider.get("suffix") or "")
            parts.append(
                '<div class="scenario-calculator" data-scenario-calculator '
                f'data-scenario-base="{result_base}" data-scenario-decimals="{decimals}" '
                f'data-scenario-prefix="{_esc(prefix)}" '
                f'data-scenario-input-prefix="{_esc(slider_prefix)}" '
                f'data-scenario-input-suffix="{_esc(slider_suffix)}">'
            )
            parts.append(f'<div class="sc-instruction">{_esc(instruction)}</div>')
            parts.append('<div class="sc-tabs" role="group" aria-label="切换情景对象">')
            for index, tab in enumerate(tabs):
                active = " active" if index == 0 else ""
                pressed = "true" if index == 0 else "false"
                parts.append(
                    f'<button type="button" class="sc-tab{active}" data-scenario-tab="{index}" '
                    f'aria-pressed="{pressed}">{_esc(tab.get("label") or f"对象 {index + 1}")}</button>'
                )
            parts.append('</div>')
            for index, tab in enumerate(tabs):
                hidden = "" if index == 0 else " hidden"
                metrics = [x for x in (tab.get("metrics") or []) if isinstance(x, dict)]
                parts.append(f'<div class="sc-platform" data-scenario-panel="{index}"{hidden}>')
                parts.append('<div class="sc-metrics">')
                for metric in metrics:
                    parts.append('<div class="sc-metric">')
                    parts.append(f'<div class="sc-metric-label">{_esc(metric.get("label") or "指标")}</div>')
                    parts.append(f'<div class="sc-metric-value">{_esc(metric.get("value") or "")}</div>')
                    if metric.get("note"):
                        parts.append(f'<div class="sc-metric-note">{_esc(metric.get("note"))}</div>')
                    parts.append('</div>')
                parts.append('</div></div>')
            parts.append('<div class="sc-control">')
            slider_label = str(slider.get("label") or "调整情景假设")
            parts.append(f'<span class="sc-control-label">{_esc(slider_label)}</span>')
            parts.append(
                f'<input type="range" data-scenario-input aria-label="{_esc(slider_label)}" '
                f'min="{slider_min:g}" max="{slider_max:g}" step="{slider_step:g}" value="{slider_value:g}">'
            )
            parts.append(
                f'<output class="sc-input-value" data-scenario-input-value>'
                f'{_esc(slider_prefix)}{slider_value:.2f}{_esc(slider_suffix)}</output>'
            )
            parts.append('</div><div class="sc-result">')
            parts.append(f'<span class="sc-result-label">{_esc(result.get("label") or "情景结果")}</span>')
            parts.append(f'<output class="sc-result-value" data-scenario-result>{_esc(prefix)}{initial_result:.{decimals}f}</output>')
            parts.append('</div>')
            if formula_note:
                parts.append(f'<div class="sc-formula">{_esc(formula_note)}</div>')
            parts.append(f'<div class="sc-caption">{_esc(caption)}</div></div>')

    elif t == "capacity_curve":
        question = data.get("question") or data.get("reader_question") or "变量继续增强时，结果会怎样变化？"
        axis_label = data.get("axis_label") or "变量强度"
        result_label = data.get("result_label") or "结果表现"
        states = [x for x in (data.get("states") or []) if isinstance(x, dict)]
        caption = data.get("caption") or "定性关系示意；具体转折点会随条件变化，不是通用预测器。"
        if 3 <= len(states) <= 5:
            positions = []
            for index, state in enumerate(states):
                try:
                    position = float(state.get("position"))
                except (TypeError, ValueError):
                    position = index * 100 / max(len(states) - 1, 1)
                positions.append(min(max(position, 0), 100))
            parts.append('<div class="capacity-curve" data-capacity-curve>')
            parts.append(f'<div class="cc-question">{_esc(question)}</div>')
            parts.append('<div class="cc-stage" aria-hidden="true">')
            parts.append(f'<span class="cc-axis-y">{_esc(result_label)}</span><span class="cc-axis-x">{_esc(axis_label)}</span>')
            parts.append('<div class="cc-points">')
            for state in states:
                parts.append(
                    '<span class="cc-point"><span class="cc-point-dot"></span>'
                    f'{_esc(state.get("label") or "阶段")}</span>'
                )
            parts.append('</div></div><div class="cc-control">')
            parts.append(
                '<input type="range" min="0" max="100" step="1" value="50" '
                f'aria-label="{_esc(axis_label)}" data-capacity-input>'
            )
            nearest = min(range(len(states)), key=lambda i: abs(positions[i] - 50))
            parts.append(f'<output class="cc-current" data-capacity-label>{_esc(states[nearest].get("label") or "阶段")}</output>')
            parts.append('</div>')
            parts.append(
                f'<div class="cc-result" data-capacity-result>{_esc(states[nearest].get("result") or "")}</div>'
            )
            for state, position in zip(states, positions):
                parts.append(
                    f'<span hidden data-capacity-state data-position="{position:g}" '
                    f'data-label="{_esc(state.get("label") or "阶段")}" '
                    f'data-result="{_esc(state.get("result") or "")}"></span>'
                )
            parts.append(f'<div class="cc-caption">{_esc(caption)}</div></div>')

    elif t == "cost_ledger":
        question = data.get("question") or data.get("reader_question") or "哪些成本被计入时，结论会改变？"
        cost_labels = [str(x).strip() for x in (data.get("cost_labels") or []) if str(x).strip()]
        scenarios = [x for x in (data.get("scenarios") or []) if isinstance(x, dict)]
        boundary = data.get("boundary") or "不同成本口径不能直接混为同一个结论。"
        if cost_labels and 2 <= len(scenarios) <= 6:
            parts.append('<div class="cost-ledger" data-cost-ledger>')
            parts.append(f'<div class="cl-question">{_esc(question)}</div>')
            parts.append('<div class="cl-tabs" role="group" aria-label="切换成本计算方式">')
            for index, scenario in enumerate(scenarios):
                active = " active" if index == 0 else ""
                pressed = "true" if index == 0 else "false"
                parts.append(
                    f'<button type="button" class="cl-tab{active}" data-cost-tab="{index}" '
                    f'aria-pressed="{pressed}">{_esc(scenario.get("label") or f"情景 {index + 1}")}</button>'
                )
            parts.append('</div>')
            for index, scenario in enumerate(scenarios):
                hidden = "" if index == 0 else " hidden"
                included = {str(x).strip() for x in (scenario.get("included") or [])}
                parts.append(f'<div class="cl-panel" data-cost-panel="{index}"{hidden}>')
                parts.append('<div class="cl-included">')
                for label in cost_labels:
                    state_class = " included" if label in included else ""
                    state_text = "计入" if label in included else "不计入"
                    parts.append(f'<span class="cl-cost{state_class}">{_esc(label)} · {state_text}</span>')
                parts.append('</div>')
                parts.append(f'<div class="cl-verdict">{_esc(scenario.get("verdict") or "")}</div>')
                parts.append(f'<div class="cl-explanation">{_esc(scenario.get("explanation") or "")}</div></div>')
            parts.append(f'<div class="cl-boundary">{_esc(boundary)}</div></div>')

    return "".join(parts)


