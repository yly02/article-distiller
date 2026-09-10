"""把原文交给大模型，输出结构化解读 JSON。"""

from .llm import _call_json, _serialize_draft, _serialize_research_ledger
from .pipeline import (
    _apply_article_patch,
    _build_draft_context,
    _load_ccswitch_config,
    _pipeline_fingerprint,
    _stable_media_fingerprint,
    build_manual_prompt,
    distill,
    resolve_llm_settings,
)
from .prompts import _editorial_review_prompt_for_modes

__all__ = [
    "distill",
    "build_manual_prompt",
    "resolve_llm_settings",
    "_editorial_review_prompt_for_modes",
    "_call_json",
    "_apply_article_patch",
    "_build_draft_context",
    "_load_ccswitch_config",
    "_pipeline_fingerprint",
    "_serialize_draft",
    "_serialize_research_ledger",
    "_stable_media_fingerprint",
]
