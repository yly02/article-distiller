"""章节组装与整页 HTML。"""
from __future__ import annotations

from typing import Any

from fetcher import Article

from .blocks import (
    _render_ai_illustration,
    _render_case_story,
    _render_experiment,
    _render_listening_card,
    _render_number_story,
    _render_source_media,
)
from .chrome import (
    _build_margin_rail,
    _insert_analogies_into_content,
    _render_analogies_inline,
    _render_category_tags,
    _render_margin_citations,
    _render_rec_reason,
    _render_source_panel,
    _render_toc,
    _section_display_title,
    _section_dom_id,
)
from .css import _CSS
from .text import _esc, _render_prose_paragraphs
from .visuals import _render_visual

def _render_section(
    sec: dict,
    idx: int,
    visuals: list,
    experiments: list | None = None,
    case_stories: list | None = None,
    source_media: list | None = None,
    illustrations: list | None = None,
    number_stories: list | None = None,
    listening_cards: list | None = None,
    term_refs: list[dict] | None = None,
    margin_citations: list[dict] | None = None,
) -> str:
    """渲染正文段落，并用编号把来源引文关联到右侧旁注。"""
    title = _esc(_section_display_title(sec))
    content = sec.get("content") or ""
    analogies = sec.get("analogies") or []
    transition_hook = str(sec.get("transition_hook") or "").strip()

    parts = []
    if title:
        parts.append(f'<h2 id="{_section_dom_id(sec, idx)}">{title}</h2>')
    leftover_analogies = analogies
    if content:
        content, leftover_analogies = _insert_analogies_into_content(content, analogies)
        parts.append(_render_prose_paragraphs(content, term_refs))
    parts.append(_render_analogies_inline(leftover_analogies))
    # Terminology and full quotations live in the off-flow margin rail.
    parts.append(_render_margin_citations(margin_citations or []))

    for item in source_media or []:
        parts.append(_render_source_media(item))
    for item in illustrations or []:
        parts.append(_render_ai_illustration(item))

    # 先给读者结论型视觉，再提供数字卡与可展开实验细节。
    for v in visuals:
        parts.append(_render_visual(v))

    for item in number_stories or []:
        parts.append(_render_number_story(item))
    for card in listening_cards or []:
        parts.append(_render_listening_card(card))

    for story in case_stories or []:
        parts.append(_render_case_story(story))
    for experiment in experiments or []:
        parts.append(_render_experiment(experiment))

    if transition_hook:
        parts.append(f'<p class="transition-hook">{_esc(transition_hook)}</p>')

    return "".join(parts)


def _assign_visuals_to_sections(sections: list, visuals: list) -> tuple[dict[int, list], list]:
    """把每个视觉组件最多分配一次；显式锚点优先，关键词仅作兼容回退。"""
    assigned: dict[int, list] = {i: [] for i in range(len(sections))}
    leftovers = []
    for visual in visuals:
        target = None
        has_explicit_anchor = any(
            key in visual and visual.get(key) not in (None, "")
            for key in ("after_section_id", "section_index", "section_tag")
        )

        anchor_id = str(visual.get("after_section_id") or "").strip()
        if anchor_id:
            for i, section in enumerate(sections):
                raw_id = str(section.get("id") or "").strip()
                if anchor_id in {raw_id, _section_dom_id(section, i), f"sec-{i}"}:
                    target = i
                    break

        if target is None and "section_index" in visual:
            raw_index = visual.get("section_index")
            if isinstance(raw_index, int) and not isinstance(raw_index, bool) and 0 <= raw_index < len(sections):
                target = raw_index

        anchor_tag = str(visual.get("section_tag") or "").strip().casefold()
        if target is None and anchor_tag:
            for i, section in enumerate(sections):
                if str(section.get("tag") or "").strip().casefold() == anchor_tag:
                    target = i
                    break

        if target is None and not has_explicit_anchor:
            visual_title = str(visual.get("title") or "").casefold()
            for i, section in enumerate(sections):
                tag = str(section.get("tag") or "").strip().casefold()
                title = str(section.get("title") or "").strip().casefold()
                keywords = [word for word in re.split(r"\s+", title) if len(word) > 2]
                if (tag and tag in visual_title) or any(word in visual_title for word in keywords):
                    target = i
                    break

        if target is None:
            leftovers.append(visual)
        else:
            assigned[target].append(visual)
    return assigned, leftovers


def _render_action_card(card: dict) -> str:
    if not card:
        return ""
    items = card.get("items") or []
    code_block = card.get("code_block") or ""
    if not items and not code_block:
        return ""
    parts = ['<div class="action-card">']
    if items:
        li = "".join(f"<li>{_esc(item)}</li>" for item in items)
        parts.append(f'<ul class="action-items">{li}</ul>')
    if code_block:
        parts.append(f'<pre class="action-code">{_esc(code_block)}</pre>')
    parts.append('</div>')
    return "".join(parts)


def _render_takeaway_list(items: list) -> str:
    """文末打勾清单会重复速览和结尾，不渲染。"""
    return ""


def _compose_quick_scan(quick_scan, recommendation_reason: str) -> list[str]:
    """速览第二条承担“为什么值得看”；旧的推荐理由并进来，不另开一块。"""
    points = [str(item).strip() for item in (quick_scan or []) if str(item).strip()][:3]
    reason = str(recommendation_reason or "").strip()
    if not reason:
        return points
    if any(reason == point or reason in point or point in reason for point in points):
        return points
    if not points:
        return [reason]
    if len(points) == 1:
        return [points[0], reason]
    if len(points) == 2:
        return [points[0], reason, points[1]]
    return points


def _render_quick_scan(items: list) -> str:
    points = [str(item).strip() for item in items if str(item).strip()][:3]
    if not points:
        return ""
    return (
        '<section class="quick-scan" aria-labelledby="quick-scan-title">'
        '<div class="quick-scan-title" id="quick-scan-title">一分钟速览</div>'
        '<ul class="quick-scan-list">'
        + "".join(f"<li>{_esc(point)}</li>" for point in points)
        + "</ul></section>"
    )


def _render_evidence_gallery(items: list) -> str:
    figures = []
    for item in items:
        if not isinstance(item, dict) or item.get("registered") is not True:
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        caption = str(item.get("caption") or item.get("section_title") or "原始证据").strip()
        source_url = str(item.get("source_url") or "").strip()
        media_type = str(item.get("type") or "image").lower()
        preview_url = str(item.get("poster_url") or url).strip()
        if media_type == "video" and not item.get("poster_url"):
            media = '<div class="number-context">视频证据</div>'
        else:
            media = f'<img src="{_esc(preview_url)}" alt="{_esc(caption)}" loading="lazy" decoding="async">'
        media_link_label = "查看视频" if media_type == "video" else "查看原图"
        links = [f'<a href="{_esc(url)}" target="_blank" rel="noopener">{media_link_label}</a>']
        if source_url:
            links.append(f'<a href="{_esc(source_url)}" target="_blank" rel="noopener">来源页面</a>')
        source_label = str(item.get("source_label") or "").strip()
        source_prefix = "视频来源" if media_type == "video" else "图内来源"
        label_html = f'<br>{source_prefix}：{_esc(source_label)}' if source_label else ""
        figures.append(
            f'<figure data-media-id="{_esc(item.get("media_id") or "")}">'
            f'{media}<figcaption>{_esc(caption)}{label_html}<br>{" · ".join(links)}</figcaption></figure>'
        )
    if not figures:
        return ""
    return (
        '<details class="evidence-gallery"><summary>原始证据图库 '
        f'({len(figures)})</summary><div class="evidence-gallery-grid">'
        f'{"".join(figures)}</div></details>'
    )


# ── 主渲染函数 ─────────────────────────────────────────────


def render_html(article: Article, distilled: dict) -> str:
    d_title = distilled.get("distilled_title") or "AI \u84B8\u998F\u89E3\u8BFB"
    one_liner = distilled.get("one_liner") or ""
    category_tags = distilled.get("category_tags") or []
    source_bias = distilled.get("source_bias_declaration") or ""
    sections = distilled.get("sections") or []
    recommendation_reason = distilled.get("recommendation_reason") or ""
    quick_scan = distilled.get("quick_scan") or []
    key_points = distilled.get("key_points") or []
    fact_check = distilled.get("fact_check") or []
    action_card = distilled.get("action_card") or {}
    takeaway_list = distilled.get("takeaway_list") or []
    visuals = distilled.get("visuals") or []
    experiments = distilled.get("experiment_ledger") or []
    case_stories = distilled.get("case_stories") or []
    source_media = distilled.get("source_media") or []
    number_stories = distilled.get("number_stories") or []
    listening_cards = distilled.get("listening_cards") or []
    evidence_gallery = distilled.get("evidence_gallery") or []
    illustrations = distilled.get("illustration_plan") or []
    source_notes = distilled.get("source_notes") or ""
    site_note = distilled.get("site_note") or ""
    further_reading = distilled.get("further_reading") or []
    background = distilled.get("background") or ""

    # 向后兼容
    if not sections and key_points:
        sections = [
            {"tag": "", "title": p.get("title", ""), "content": p.get("insight", ""),
             "archive_original": [{"original": "", "translation": p.get("evidence", "")}]}
            for p in key_points
        ]
    # 构建各部分
    tags_html = _render_category_tags(category_tags)
    rec_reason_html = _render_rec_reason(recommendation_reason)
    quick_scan_html = _render_quick_scan(_compose_quick_scan(quick_scan, recommendation_reason))
    toc_html = _render_toc(sections)
    glossary_html, term_refs, margin_citations = _build_margin_rail(sections)

    # 正文 = 段落 + 一次性分配的视觉组件；未命中锚点的组件保留在末尾。
    section_visuals, leftover_items = _assign_visuals_to_sections(sections, visuals)
    section_experiments, leftover_experiments = _assign_visuals_to_sections(sections, experiments)
    section_cases, leftover_cases = _assign_visuals_to_sections(sections, case_stories)
    section_media, _leftover_media = _assign_visuals_to_sections(
        sections,
        [item for item in source_media if isinstance(item, dict) and item.get("registered") is True],
    )
    section_illustrations, leftover_illustrations = _assign_visuals_to_sections(
        sections,
        [item for item in illustrations if isinstance(item, dict) and item.get("status") == "generated"],
    )
    section_numbers, leftover_numbers = _assign_visuals_to_sections(sections, number_stories)
    section_listening, leftover_listening = _assign_visuals_to_sections(
        sections,
        [item for item in listening_cards if isinstance(item, dict) and item.get("registered") is True],
    )
    sections_html = "".join(
        _render_section(
            section,
            i,
            section_visuals[i],
            section_experiments[i],
            section_cases[i],
            section_media[i],
            section_illustrations[i],
            section_numbers[i],
            section_listening[i],
            term_refs[i],
            margin_citations[i],
        )
        for i, section in enumerate(sections)
    )
    leftover_depth = "".join(_render_case_story(x) for x in leftover_cases)
    leftover_depth += "".join(_render_experiment(x) for x in leftover_experiments)
    leftover_visuals = "".join(_render_visual(v) for v in leftover_items)
    leftover_visuals += "".join(_render_ai_illustration(v) for v in leftover_illustrations)
    leftover_visuals += "".join(_render_number_story(v) for v in leftover_numbers)
    leftover_visuals += "".join(_render_listening_card(v) for v in leftover_listening)

    action_html = _render_action_card(action_card)
    takeaway_html = _render_takeaway_list(takeaway_list)
    inline_media_ids = {
        str(item.get("media_id") or "").strip()
        for item in source_media
        if isinstance(item, dict)
        and item.get("registered") is True
        and str(item.get("media_id") or "").strip()
    }
    evidence_gallery_html = _render_evidence_gallery([
        item for item in evidence_gallery
        if not isinstance(item, dict)
        or str(item.get("media_id") or "").strip() not in inline_media_ids
    ])
    source_panel_html = _render_source_panel(
        article,
        further_reading,
        # source_notes/fact_check/editorial_quality are audit-only.  The page
        # may show a short site_note or a natural bias note, never the audit
        # explanation or quality report itself.
        site_note or source_bias,
        fact_check,
    )

    # 组装
    body_html = ""
    if sections_html or leftover_depth or leftover_visuals:
        body_html = f'<div class="article-body">{sections_html}{leftover_depth}{leftover_visuals}</div>'

    # 背景补充（向后兼容）
    background_html = ""
    if background and not any(s.get("content") == background for s in sections):
        background_html = f'<div class="article-body"><h2>\u80CC\u666F\u8865\u5145</h2><p>{_esc(background)}</p></div>'

    one_liner_html = f'<div class="sub-title">{_esc(one_liner)}</div>' if one_liner else ""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(d_title)}</title>
<style>{_CSS}</style>
</head>
<body>

<div class="theme-switcher">
  <div class="theme-btn theme-light active" onclick="setTheme('light')" title="\u4EAE\u8272"></div>
  <div class="theme-btn theme-dark" onclick="setTheme('dark')" title="\u6697\u8272"></div>
  <div class="theme-btn theme-sepia" onclick="setTheme('sepia')" title="\u62A4\u773C"></div>
</div>

<a class="scroll-top" id="scrollTop" href="#article-top" aria-label="返回文章顶部" title="返回文章顶部">\u2191</a>

<div class="wrap">
  <header id="article-top">
    {tags_html}
    <h1>{_esc(d_title)}</h1>
    {one_liner_html}
  </header>

  {rec_reason_html}
  {quick_scan_html}
  {toc_html}
  {glossary_html}
  {body_html}
  {background_html}
  {action_html}
  {takeaway_html}
  {evidence_gallery_html}
  {source_panel_html}

</div>

<script>
function setTheme(t){{
  document.body.setAttribute('data-theme',t);
  document.querySelectorAll('.theme-btn').forEach(b=>b.classList.remove('active'));
  document.querySelector('.theme-'+t).classList.add('active');
  try{{localStorage.setItem('ad-theme',t)}}catch(e){{}}
}}
(function(){{
  try{{
    var t=localStorage.getItem('ad-theme');
    if(t) setTheme(t);
  }}catch(e){{}}
}})();
window.addEventListener('scroll',function(){{
  var b=document.getElementById('scrollTop');
  if(window.scrollY>400) b.classList.add('show'); else b.classList.remove('show');
}});
document.getElementById('scrollTop').addEventListener('click',function(event){{
  var target=document.getElementById('article-top');
  if(!target) return;
  event.preventDefault();
  target.scrollIntoView({{behavior:'smooth',block:'start'}});
}});
function syncReadingRails(){{
  var wide=window.matchMedia('(min-width:1240px)').matches;
  document.querySelectorAll('[data-reading-rail]').forEach(function(rail){{rail.open=wide}});
}}
document.querySelectorAll('[data-reading-rail]').forEach(function(rail){{
  rail.addEventListener('toggle',function(){{
    if(!rail.open || window.matchMedia('(min-width:1240px)').matches) return;
    document.querySelectorAll('[data-reading-rail]').forEach(function(other){{
      if(other!==rail) other.open=false;
    }});
  }});
}});
var railMedia=window.matchMedia('(min-width:1240px)');
if(railMedia.addEventListener) railMedia.addEventListener('change',syncReadingRails);
syncReadingRails();
if('IntersectionObserver' in window){{
  var tocLinks=Array.from(document.querySelectorAll('.toc-link[data-section-target]'));
  var byId=new Map(tocLinks.map(function(link){{return [link.dataset.sectionTarget,link]}}));
  var observer=new IntersectionObserver(function(entries){{
    entries.forEach(function(entry){{
      if(!entry.isIntersecting) return;
      tocLinks.forEach(function(link){{link.classList.remove('active')}});
      var link=byId.get(entry.target.id); if(link) link.classList.add('active');
    }});
  }},{{rootMargin:'-18% 0px -68% 0px',threshold:0}});
  byId.forEach(function(_link,id){{var heading=document.getElementById(id);if(heading) observer.observe(heading)}});
}}
function positionTermPopover(wrapper){{
  var marker=wrapper&&wrapper.querySelector('.term-marker');
  var popover=wrapper&&wrapper.querySelector('.term-popover');
  if(!marker || !popover) return;
  var rect=marker.getBoundingClientRect();
  var half=Math.min(150,Math.max(120,(window.innerWidth-24)/2));
  var article=wrapper.closest('.article-body');
  var bounds=article?article.getBoundingClientRect():{{left:12,right:window.innerWidth-12}};
  var minCenter=Math.max(half+12,bounds.left+half);
  var maxCenter=Math.min(window.innerWidth-half-12,bounds.right-half);
  if(maxCenter<minCenter){{minCenter=half+12;maxCenter=window.innerWidth-half-12}}
  var center=Math.max(minCenter,Math.min(maxCenter,rect.left+rect.width/2));
  var placeBelow=rect.top<190;
  wrapper.style.setProperty('--term-popover-left',(center-rect.left)+'px');
  wrapper.style.setProperty('--term-popover-top',(placeBelow?rect.height:0)+'px');
  popover.classList.toggle('below',placeBelow);
}}
document.querySelectorAll('.term-marker-wrap').forEach(function(wrapper){{
  wrapper.addEventListener('mouseenter',function(){{positionTermPopover(wrapper)}});
  wrapper.addEventListener('focusin',function(){{positionTermPopover(wrapper)}});
}});
function closeTermPopovers(except){{
  document.querySelectorAll('.term-marker-wrap.is-open').forEach(function(wrapper){{
    if(wrapper===except) return;
    wrapper.classList.remove('is-open');
    var button=wrapper.querySelector('[data-term-popover-toggle]');
    if(button){{
      button.setAttribute('aria-expanded','false');
      if(document.activeElement===button) button.blur();
    }}
  }});
}}
document.addEventListener('click',function(event){{
  var openToc=document.querySelector('.toc-card[open]');
  if(openToc && !event.target.closest('.toc-card')) openToc.open=false;
  var openQuotes=document.querySelector('.glossary-rail[open]');
  if(openQuotes && !window.matchMedia('(min-width:1240px)').matches && !event.target.closest('.glossary-rail') && !event.target.closest('[data-margin-note-target]')){{
    openQuotes.open=false;
    document.querySelectorAll('.margin-note.is-highlighted').forEach(function(item){{
      item.classList.remove('is-highlighted');
    }});
  }}
  var termButton=event.target.closest('[data-term-popover-toggle]');
  if(termButton){{
    event.preventDefault();
    var wrapper=termButton.closest('.term-marker-wrap');
    var shouldOpen=!wrapper.classList.contains('is-open');
    closeTermPopovers(wrapper);
    wrapper.classList.toggle('is-open',shouldOpen);
    termButton.setAttribute('aria-expanded',shouldOpen?'true':'false');
    if(shouldOpen) positionTermPopover(wrapper);
    else termButton.blur();
    return;
  }}
  if(!event.target.closest('.term-popover')) closeTermPopovers();
  var citation=event.target.closest('[data-margin-note-target]');
  if(citation){{
    event.preventDefault();
    var note=document.getElementById(citation.getAttribute('data-margin-note-target'));
    var rail=note&&note.closest('[data-reading-rail="margin"]');
    if(!note || !rail) return;
    if(!window.matchMedia('(min-width:1240px)').matches) rail.open=true;
    document.querySelectorAll('.margin-note.is-highlighted').forEach(function(item){{
      item.classList.remove('is-highlighted');
    }});
    note.classList.add('is-highlighted');
    note.focus({{preventScroll:true}});
    note.scrollIntoView({{behavior:'smooth',block:'nearest'}});
    try{{history.replaceState(null,'','#'+note.id)}}catch(e){{}}
    window.setTimeout(function(){{note.classList.remove('is-highlighted')}},2200);
    return;
  }}
  var button=event.target.closest('[data-interactive-mode]');
  if(!button) return;
  var root=button.closest('[data-interactive-compare]');
  if(!root) return;
  var mode=button.getAttribute('data-interactive-mode');
  root.querySelectorAll('[data-interactive-mode]').forEach(function(item){{
    var active=item.getAttribute('data-interactive-mode')===mode;
    item.classList.toggle('active',active);
    item.setAttribute('aria-pressed',active?'true':'false');
  }});
  root.querySelectorAll('[data-interactive-state]').forEach(function(item){{
    item.hidden=item.getAttribute('data-interactive-state')!==mode;
  }});
}});
document.addEventListener('click',function(event){{
  var metricButton=event.target.closest('[data-metric-tab]');
  if(metricButton){{
    var metricRoot=metricButton.closest('[data-metric-bars]');
    if(!metricRoot) return;
    var metric=metricButton.getAttribute('data-metric-tab');
    metricRoot.querySelectorAll('[data-metric-tab]').forEach(function(item){{
      var active=item.getAttribute('data-metric-tab')===metric;
      item.classList.toggle('active',active);
      item.setAttribute('aria-pressed',active?'true':'false');
    }});
    metricRoot.querySelectorAll('[data-metric-panel]').forEach(function(item){{
      item.hidden=item.getAttribute('data-metric-panel')!==metric;
    }});
    return;
  }}
  var button=event.target.closest('[data-scenario-tab]');
  if(!button) return;
  var root=button.closest('[data-scenario-calculator]');
  if(!root) return;
  var tab=button.getAttribute('data-scenario-tab');
  root.querySelectorAll('[data-scenario-tab]').forEach(function(item){{
    var active=item.getAttribute('data-scenario-tab')===tab;
    item.classList.toggle('active',active);
    item.setAttribute('aria-pressed',active?'true':'false');
  }});
  root.querySelectorAll('[data-scenario-panel]').forEach(function(item){{
    item.hidden=item.getAttribute('data-scenario-panel')!==tab;
  }});
}});
document.querySelectorAll('[data-metric-bars]').forEach(function(root){{
  root.classList.add('metric-bars-ready');
  root.querySelectorAll('[data-metric-panel]').forEach(function(item,index){{item.hidden=index!==0;}});
}});
document.addEventListener('click',function(event){{
  var button=event.target.closest('[data-rank-tab]');
  if(!button) return;
  var root=button.closest('[data-rank-bars]');
  if(!root) return;
  var tab=button.getAttribute('data-rank-tab');
  root.querySelectorAll('[data-rank-tab]').forEach(function(item){{
    var active=item.getAttribute('data-rank-tab')===tab;
    item.classList.toggle('active',active);
    item.setAttribute('aria-pressed',active?'true':'false');
  }});
  root.querySelectorAll('[data-rank-panel]').forEach(function(item){{
    item.hidden=item.getAttribute('data-rank-panel')!==tab;
  }});
}});
document.querySelectorAll('[data-rank-bars]').forEach(function(root){{
  root.classList.add('rank-bars-ready');
  root.querySelectorAll('[data-rank-panel]').forEach(function(item,index){{item.hidden=index!==0;}});
}});
function setFlowStep(root,index){{
  var tabs=Array.from(root.querySelectorAll('[data-flow-step]'));
  var panels=Array.from(root.querySelectorAll('[data-flow-panel]'));
  if(!tabs.length || index<0 || index>=tabs.length) return;
  tabs.forEach(function(item,itemIndex){{
    var active=itemIndex===index;
    item.classList.toggle('active',active);
    item.setAttribute('aria-pressed',active?'true':'false');
  }});
  panels.forEach(function(item,itemIndex){{item.classList.toggle('active',itemIndex===index);}});
  root.setAttribute('data-flow-current',String(index));
  var prev=root.querySelector('[data-flow-prev]');
  var next=root.querySelector('[data-flow-next]');
  if(prev) prev.disabled=index===0;
  if(next) next.disabled=index===tabs.length-1;
}}
document.querySelectorAll('[data-flow-stepper]').forEach(function(root){{
  root.classList.add('flow-stepper-ready');
  setFlowStep(root,0);
}});
document.addEventListener('click',function(event){{
  var tab=event.target.closest('[data-flow-step]');
  var control=event.target.closest('[data-flow-prev],[data-flow-next]');
  var root=(tab||control)&&(tab||control).closest('[data-flow-stepper]');
  if(!root) return;
  if(tab){{setFlowStep(root,Number(tab.getAttribute('data-flow-step')));return;}}
  var current=Number(root.getAttribute('data-flow-current')||0);
  setFlowStep(root,current+(control.matches('[data-flow-prev]')?-1:1));
}});
document.querySelectorAll('[data-strategy-tabs]').forEach(function(root){{
  root.classList.add('strategy-tabs-ready');
  root.querySelectorAll('[data-strategy-panel]').forEach(function(item,index){{
    item.classList.toggle('active',index===0);
  }});
}});
document.addEventListener('click',function(event){{
  var button=event.target.closest('[data-strategy-tab]');
  if(!button) return;
  var root=button.closest('[data-strategy-tabs]');
  if(!root) return;
  var selected=button.getAttribute('data-strategy-tab');
  root.querySelectorAll('[data-strategy-tab]').forEach(function(item){{
    var active=item.getAttribute('data-strategy-tab')===selected;
    item.classList.toggle('active',active);
    item.setAttribute('aria-selected',active?'true':'false');
  }});
  root.querySelectorAll('[data-strategy-panel]').forEach(function(item){{
    item.classList.toggle('active',item.getAttribute('data-strategy-panel')===selected);
  }});
}});
document.querySelectorAll('[data-timeline-scrubber]').forEach(function(root){{
  root.classList.add('timeline-scrubber-ready');
}});
document.addEventListener('input',function(event){{
  var input=event.target.closest('[data-timeline-input]');
  if(!input) return;
  var root=input.closest('[data-timeline-scrubber]');
  var state=root&&root.querySelector('[data-timeline-event="'+input.value+'"]');
  if(!state) return;
  var time=root.querySelector('[data-timeline-time]');
  var title=root.querySelector('[data-timeline-title]');
  var description=root.querySelector('[data-timeline-description]');
  if(time) time.textContent=state.getAttribute('data-time')||'';
  if(title) title.textContent=state.getAttribute('data-title')||'';
  if(description) description.textContent=state.getAttribute('data-description')||'';
}});
document.addEventListener('click',function(event){{
  var button=event.target.closest('[data-listening-tab]');
  if(!button) return;
  var root=button.closest('[data-listening-card]');
  if(!root) return;
  var tab=button.getAttribute('data-listening-tab');
  root.querySelectorAll('[data-listening-audio]').forEach(function(audio){{audio.pause();}});
  root.querySelectorAll('[data-listening-tab]').forEach(function(item){{
    var active=item.getAttribute('data-listening-tab')===tab;
    item.classList.toggle('active',active);
    item.setAttribute('aria-selected',active?'true':'false');
    item.setAttribute('tabindex',active?'0':'-1');
  }});
  root.querySelectorAll('[data-listening-panel]').forEach(function(item){{
    item.hidden=item.getAttribute('data-listening-panel')!==tab;
  }});
}});
document.addEventListener('play',function(event){{
  if(!event.target.matches('[data-listening-audio]')) return;
  document.querySelectorAll('[data-listening-audio]').forEach(function(audio){{
    if(audio!==event.target) audio.pause();
  }});
}},true);
document.addEventListener('input',function(event){{
  var input=event.target.closest('[data-scenario-input]');
  if(!input) return;
  var root=input.closest('[data-scenario-calculator]');
  if(!root) return;
  var value=parseFloat(input.value);
  var base=parseFloat(root.getAttribute('data-scenario-base'));
  var decimals=parseInt(root.getAttribute('data-scenario-decimals')||'2',10);
  if(!Number.isFinite(value)||!Number.isFinite(base)) return;
  var inputOutput=root.querySelector('[data-scenario-input-value]');
  var resultOutput=root.querySelector('[data-scenario-result]');
  var prefix=root.getAttribute('data-scenario-prefix')||'';
  var inputPrefix=root.getAttribute('data-scenario-input-prefix')||'';
  var inputSuffix=root.getAttribute('data-scenario-input-suffix')||'';
  if(inputOutput) inputOutput.textContent=inputPrefix+value.toFixed(2)+inputSuffix;
  if(resultOutput) resultOutput.textContent=prefix+(base-value).toFixed(decimals);
}});
document.addEventListener('input',function(event){{
  var input=event.target.closest('[data-capacity-input]');
  if(!input) return;
  var root=input.closest('[data-capacity-curve]');
  if(!root) return;
  var value=Number(input.value);
  var nearest=null;
  var distance=Infinity;
  root.querySelectorAll('[data-capacity-state]').forEach(function(state){{
    var current=Math.abs(Number(state.getAttribute('data-position'))-value);
    if(current<distance){{distance=current;nearest=state;}}
  }});
  if(!nearest) return;
  var label=root.querySelector('[data-capacity-label]');
  var result=root.querySelector('[data-capacity-result]');
  if(label) label.textContent=nearest.getAttribute('data-label')||'';
  if(result) result.textContent=nearest.getAttribute('data-result')||'';
}});
document.addEventListener('click',function(event){{
  var button=event.target.closest('[data-cost-tab]');
  if(!button) return;
  var root=button.closest('[data-cost-ledger]');
  if(!root) return;
  var tab=button.getAttribute('data-cost-tab');
  root.querySelectorAll('[data-cost-tab]').forEach(function(item){{
    var active=item.getAttribute('data-cost-tab')===tab;
    item.classList.toggle('active',active);
    item.setAttribute('aria-pressed',active?'true':'false');
  }});
  root.querySelectorAll('[data-cost-panel]').forEach(function(item){{
    item.hidden=item.getAttribute('data-cost-panel')!==tab;
  }});
}});
document.addEventListener('keydown',function(event){{
  if(event.key==='Escape'){{
    closeTermPopovers();
    var openToc=document.querySelector('.toc-card[open]');
    if(openToc) openToc.open=false;
    var openQuotes=document.querySelector('.glossary-rail[open]');
    if(openQuotes && !window.matchMedia('(min-width:1240px)').matches){{
      openQuotes.open=false;
      document.querySelectorAll('.margin-note.is-highlighted').forEach(function(item){{
        item.classList.remove('is-highlighted');
      }});
    }}
  }}
}});
</script>
</body>
</html>"""
