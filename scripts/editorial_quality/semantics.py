"""主张是否被公开正文语义覆盖。"""
from __future__ import annotations

from typing import Any, Iterable

from .support import *  # noqa: F403

def _flatten_visible_text(value: Any) -> list[str]:
    """Flatten text from a known public component after its container is selected."""
    if isinstance(value, dict):
        return [text for item in value.values() for text in _flatten_visible_text(item)]
    if isinstance(value, list):
        return [text for item in value for text in _flatten_visible_text(item)]
    text = _text(value)
    return [text] if text else []


def _walk_public_text(
    value: Any,
    path: tuple[str | int, ...] = (),
) -> Iterable[tuple[tuple[str | int, ...], str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_public_text(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_public_text(child, (*path, index))
    elif isinstance(value, str) and value.strip():
        yield path, value


def _public_path(path: tuple[str | int, ...]) -> str:
    result = "$"
    for item in path:
        result += f"[{item}]" if isinstance(item, int) else f".{item}"
    return result


def _semantic_corpus(distilled: dict, mode: str) -> str:
    """Return publish-facing copy only; audit notes and research ledgers are excluded."""
    def visible_items(key: str) -> list:
        return [
            item for item in _list(distilled.get(key))
            if not isinstance(item, dict)
            or (
                item.get("suppress_visual") is not True
                and _text(item.get("display_mode")).lower() != "audit_only"
            )
        ]

    selected: list[Any] = [distilled.get("distilled_title")]
    selected.extend((
        distilled.get("quick_scan"),
        distilled.get("sections"),
        visible_items("experiment_ledger"),
        visible_items("case_stories"),
        visible_items("number_stories"),
        distilled.get("listening_cards"),
        distilled.get("visuals"),
        distilled.get("action_card"),
        distilled.get("takeaway_list"),
    ))
    return "\n".join(text for item in selected for text in _flatten_visible_text(item))


def _semantic_normalize(value: Any) -> str:
    text = _normalize_chinese_percentages(_text(value).lower())
    for pattern, replacement in SEMANTIC_ALIAS_PATTERNS:
        text = pattern.sub(replacement, text)
    return re.sub(r"[^0-9a-z%\u4e00-\u9fff.+-]+", "", text)


_CHINESE_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def _chinese_integer(value: str) -> int | None:
    """Parse the small integers normally used in percentage claims."""
    if not value:
        return None
    if all(char in _CHINESE_DIGITS for char in value):
        return int("".join(str(_CHINESE_DIGITS[char]) for char in value))
    total = 0
    current = 0
    for char in value:
        if char in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def _normalize_chinese_percentages(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        integer = _chinese_integer(match.group(1))
        fraction = match.group(2)
        if integer is None:
            return match.group(0)
        if fraction:
            digits = "".join(str(_CHINESE_DIGITS[char]) for char in fraction)
            return f"{integer}.{digits}%"
        return f"{integer}%"

    return re.sub(
        r"百分之([零〇一二两三四五六七八九十百]+)(?:点([零〇一二三四五六七八九]+))?",
        replace,
        value,
    )


def _function_signatures(value: Any) -> set[str]:
    """Extract complete code-like interfaces so prose around them may be paraphrased."""
    signatures = set()
    for match in re.findall(
        r"[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*\s*\([^)]*\)\s*[-=]>\s*[A-Za-z][A-Za-z0-9_]*",
        _text(value),
    ):
        signatures.add(re.sub(r"\s+", "", match).lower())
    return signatures


def _version_release_signatures(value: Any) -> set[str]:
    """Pair product identifiers with nearby semantic-version release numbers."""
    signatures = set()
    text = _text(value).lower()
    ignored = SEMANTIC_COMMON_LATIN | {"version", "release", "releases", "today"}
    for match in re.finditer(r"\b\d+\.\d+\.\d+\b", text):
        prefix = text[max(0, match.start() - 96):match.start()]
        identifiers = [
            token
            for token in re.findall(r"[a-z][a-z0-9_.+-]*", prefix)
            if token not in ignored and not token.replace(".", "").isdigit()
        ]
        if identifiers:
            signatures.add(f"{identifiers[-1]}@{match.group(0)}")
    return signatures


def _claim_clauses(value: Any) -> list[str]:
    clauses = [
        _text(item)
        for item in re.split(r"[，；。！？;!?]+", _text(value))
        if len(_semantic_normalize(item)) >= 3
    ]
    return clauses or ([_text(value)] if _text(value) else [])


def _exact_claim_terms(clause: str) -> list[str]:
    normalized_clause = _normalize_chinese_percentages(clause)
    numbers = re.findall(r"\d+(?:[.,]\d+)*(?:%|万|亿|[a-zA-Z]{1,5})?", normalized_clause)
    identifiers = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_.+-]*", clause):
        lowered = token.lower()
        if lowered in SEMANTIC_COMMON_LATIN:
            continue
        if len(token) >= 2 and (token != lowered or any(char.isdigit() for char in token) or lowered in {"ai", "api", "token"}):
            identifiers.append(lowered)
    return list(dict.fromkeys(numbers + identifiers))


def _semantic_ngrams(value: Any) -> list[str]:
    normalized = _semantic_normalize(value)
    grams: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        width = 3 if len(run) >= 3 else 2
        for index in range(max(0, len(run) - width + 1)):
            gram = run[index:index + width]
            if gram not in SEMANTIC_GENERIC_NGRAMS:
                grams.append(gram)
    return list(dict.fromkeys(grams))


def _audit_claim_against_corpus(claim_id: str, claim_text: str, corpus: str) -> dict:
    normalized_corpus = _semantic_normalize(corpus)
    corpus_signatures = _function_signatures(corpus)
    corpus_version_signatures = _version_release_signatures(corpus)
    clause_reports = []
    all_matched: list[str] = []
    all_missing: list[str] = []
    ratios: list[float] = []

    for clause in _claim_clauses(claim_text):
        exact_terms = _exact_claim_terms(clause)
        missing_exact = [term for term in exact_terms if _semantic_normalize(term) not in normalized_corpus]
        claim_signatures = _function_signatures(clause)
        claim_version_signatures = _version_release_signatures(clause)
        signatures_matched = (
            (bool(claim_signatures) and claim_signatures <= corpus_signatures)
            or (
                bool(claim_version_signatures)
                and claim_version_signatures <= corpus_version_signatures
            )
        )
        grams = _semantic_ngrams(clause)
        matched_grams = [term for term in grams if term in normalized_corpus]
        ratio = len(matched_grams) / len(grams) if grams else (1.0 if exact_terms else 0.0)
        # Short paraphrases may retain only one canonical three-character phrase.
        threshold = 0.33 if len(grams) >= 3 else 0.5
        # 中文数字口径常会在正文中换序表达，例如“单次最多支持输入 30 张图片”
        # 与“单次输入上限是 30 张图片”。只要数字、数量单位、对象和“上限/最多”
        # 语义都出现，就视为同一条保守的指标主张，避免把自然改写误报为漏写。
        metric_equivalent = False
        if exact_terms and not missing_exact and re.search(r"最多|上限|最高|提升至|增加", clause):
            metric_equivalent = bool(
                re.search(r"最多|上限|最高|提升至|增加", normalized_corpus)
                and any(
                    anchor in normalized_corpus
                    for anchor in ("张图片", "段视频", "段音频", "参考素材", "单次输入")
                    if anchor in _semantic_normalize(clause)
                )
            )
        numeric_anchor = bool(exact_terms) and not missing_exact and bool(re.search(r"\d", clause))
        matched = not missing_exact and (
            signatures_matched
            or ratio >= threshold
            or (not grams and bool(exact_terms))
            or metric_equivalent
            or (numeric_anchor and ratio >= 0.08)
        )
        matched_terms = exact_terms + matched_grams
        missing_terms = missing_exact + ([term for term in grams if term not in normalized_corpus] if not matched else [])
        clause_reports.append({
            "text": clause,
            "matched": matched,
            "match_ratio": round(ratio, 3),
            "required_exact_terms": exact_terms,
            "matched_signatures": sorted(
                (claim_signatures & corpus_signatures)
                | (claim_version_signatures & corpus_version_signatures)
            ),
            "matched_terms": list(dict.fromkeys(matched_terms))[:12],
            "missing_terms": list(dict.fromkeys(missing_terms))[:12],
        })
        ratios.append(ratio)
        all_matched.extend(matched_terms)
        all_missing.extend(missing_terms)

    matched = bool(clause_reports) and all(item["matched"] for item in clause_reports)
    return {
        "claim_id": claim_id,
        "claim": claim_text,
        "matched": matched,
        "match_ratio": round(sum(ratios) / len(ratios), 3) if ratios else 0.0,
        "matched_terms": list(dict.fromkeys(all_matched))[:20],
        "missing_terms": list(dict.fromkeys(all_missing))[:20],
        "clauses": clause_reports,
    }


def semantic_claim_coverage(
    distilled: dict,
    research: dict,
    required_modes: Iterable[str] = ("full",),
) -> dict:
    """Deterministic lexical-semantic coverage check for high-priority claims.

    This catches material omissions and missing numeric/model anchors. It is not a
    substitute for the LLM editorial review and deliberately avoids audit-only text.
    """
    modes = [mode for mode in required_modes if mode in OUTPUT_MODES]
    claims = [item for item in _list(research.get("claims")) if isinstance(item, dict)]
    omissions = distilled.get("editorial_coverage") if isinstance(distilled.get("editorial_coverage"), dict) else {}
    omitted_ids = _claim_ids([
        item for item in _list(omissions.get("omitted_claims"))
        if isinstance(item, dict) and _text(item.get("reason"))
    ])
    high_claims_all = [
        item for item in claims
        if _text(item.get("id"))
        and _text(item.get("importance")).lower() == "high"
        and _text(item.get("id")) not in omitted_ids
    ]
    uncheckable_ids = [
        _text(item.get("id")) for item in high_claims_all
        if len(_semantic_normalize(item.get("claim") or item.get("text") or item.get("statement"))) < 6
    ]
    high_claims = [item for item in high_claims_all if _text(item.get("id")) not in uncheckable_ids]

    by_mode: dict[str, list[dict]] = {}
    missing_by_mode: dict[str, list[str]] = {}
    for mode in modes:
        corpus = _semantic_corpus(distilled, mode)
        reports = []
        for item in high_claims:
            claim_id = _text(item.get("id"))
            claim_text = _text(item.get("claim") or item.get("text") or item.get("statement"))
            report = _audit_claim_against_corpus(claim_id, claim_text, corpus)
            reports.append(report)
        by_mode[mode] = reports
        missing_by_mode[mode] = [item["claim_id"] for item in reports if not item["matched"]]

    missing_ids = sorted({claim_id for ids in missing_by_mode.values() for claim_id in ids})
    return {
        "checked_high_claim_count": len(high_claims),
        "uncheckable_high_claim_ids": uncheckable_ids,
        "modes": by_mode,
        "missing_by_mode": missing_by_mode,
        "semantically_missing_high_claim_ids": missing_ids,
    }


