"""What a rewrite must keep, and what it must not add: the Desktop plugin's
preservation and intent checks, for the stock-Hermes fallback.

A line-for-line port of ``dev/src/preservation.ts``. The intent rules themselves are
not copied: they are read from ``shared.json``, which ``dev/build.mjs`` exports
from ``dev/src/intent.ts``. ``dev/test/python/test_parity.py`` holds this module
to the TypeScript checker's verdicts on ``dev/test/parity/inputs.json``.

Like the TypeScript original it under-approximates on purpose: it never claims
meaning is preserved, only that these items were not silently dropped, and that
these kinds of action were not added.

JavaScript regex semantics are kept with ``re.ASCII`` (JS ``\\w``, ``\\d`` and ``\\b``
are ASCII-only).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_A = re.ASCII

FENCE_RE = re.compile(r"(```|~~~)[^\n]*\n([\s\S]*?)\1", _A)
REFERENCE_RE = re.compile(r"(?<![\w/])@[a-z][a-z0-9-]*:(?:`[^`\n]+`|\"[^\"\n]+\"|'[^'\n]+'|\S+)", _A | re.I)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`", _A)
URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>\"'`]+", _A | re.I)
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?)\]}'\"»”’]+$", _A)
LEADING_PUNCT_RE = re.compile(r"^[(\[{'\"«“‘]+", _A)

FILE_EXTENSIONS = frozenset(
    (
        "ts tsx js jsx mjs cjs json jsonc md mdx py pyi rs go java kt kts swift c h cc cpp hpp cs rb php sh zsh bash fish "
        "ps1 yml yaml toml ini cfg conf env lock txt csv tsv html htm css scss less sql xml svg png jpg jpeg gif webp pdf "
        "doc docx xls xlsx ppt pptx ipynb vue svelte dart lua r pl ex exs zig nix gradle plist log dockerfile proto graphql"
    ).split()
)

NEGATION_RE = re.compile(r"\b(?:not|no|never|none|nor|without|avoid|cannot)\b|n['’]t\b", _A | re.I)
REQUIREMENT_RE = re.compile(r"\b(?:must|only|exactly|always|required?|ensure|mandatory|strictly)\b", _A | re.I)

NUMBER_RE = re.compile(r"[A-Za-z]*\d+(?:[.,:]\d+)*[A-Za-z%]*", _A)
WHITESPACE_RE = re.compile(r"\s+")


def _blank(text: str, pattern: re.Pattern[str]) -> str:
    """Replace each match with spaces of the same length."""
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def _strip_punct(token: str) -> str:
    return TRAILING_PUNCT_RE.sub("", LEADING_PUNCT_RE.sub("", token))


def _is_path(token: str) -> bool:
    if re.match(r"[A-Za-z]:\\\S+", token, _A) or re.match(r"(?:~|\.{1,2})?/[^\s/]", token, _A):
        return True
    slashes = token.count("/")
    ext = re.search(r"\.([A-Za-z0-9]{1,10})$", token, _A)
    known = bool(ext and ext.group(1).lower() in FILE_EXTENSIONS)
    if slashes >= 1 and re.fullmatch(r"[\w.@~-]+(?:/[\w.@~-]+)+/?", token, _A):
        return slashes >= 2 or known
    return known and bool(re.fullmatch(r"[\w-]+(?:\.[\w-]+)*\.[A-Za-z0-9]{1,10}", token, _A))


def _is_identifier(token: str) -> bool:
    return bool(
        (
            re.search(r"[A-Za-z]", token)
            and re.search(r"\d", token)
            and re.search(r"[-_.:]", token)
            and re.fullmatch(r"[A-Za-z0-9][\w.:+-]*[A-Za-z0-9]", token, _A)
        )
        or re.fullmatch(r"[A-Za-z][A-Za-z]*\d[A-Za-z0-9]*", token)
        or re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+", token)
        or re.fullmatch(r"[a-z]+(?:[A-Z][a-z0-9]*)+", token)
        or re.fullmatch(r"[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+", token)
    )


def _is_kebab_name(token: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+", token))


def _collect(original: str) -> tuple[list[dict[str, str]], str]:
    items: list[dict[str, str]] = []

    def add(kind: str, value: str, severity: str = "blocking") -> None:
        if value.strip():
            items.append({"kind": kind, "severity": severity, "value": value})

    for m in FENCE_RE.finditer(original):
        add("code-block", re.sub(r"\n$", "", m.group(2)))
    rest = _blank(original, FENCE_RE)

    for m in REFERENCE_RE.finditer(rest):
        value = m.group(0)
        add("reference", value if re.match(r"@[^:]+:[`\"']", value) else _strip_punct(value))
    rest = _blank(rest, REFERENCE_RE)

    for m in INLINE_CODE_RE.finditer(rest):
        add("inline-code", m.group(1))
    rest = _blank(rest, INLINE_CODE_RE)

    for m in URL_RE.finditer(rest):
        add("url", TRAILING_PUNCT_RE.sub("", m.group(0)))
    rest = _blank(rest, URL_RE)

    for raw in WHITESPACE_RE.split(rest):
        token = _strip_punct(raw)
        if not token:
            continue
        if _is_path(token):
            add("path", token)
        elif _is_identifier(token):
            add("identifier", token)
        elif _is_kebab_name(token):
            add("name", token, "review")
        else:
            for number in NUMBER_RE.findall(token):
                add("number", number)

    return items, rest


def _contains(candidate: str, item: dict[str, str]) -> bool:
    if item["kind"] in ("code-block", "reference", "url", "inline-code"):
        return item["value"] in candidate
    flags = _A | (re.I if item["kind"] == "number" else 0)
    return re.search(rf"(?<![\w.]){re.escape(item['value'])}(?![\w]|\.\d)", candidate, flags) is not None


def _prose_of(text: str) -> str:
    for pattern in (FENCE_RE, REFERENCE_RE, INLINE_CODE_RE, URL_RE):
        text = _blank(text, pattern)
    return text


# ── intent (rules from shared.json) ─────────────────────────────────────────


def _compile(pattern: dict[str, str]) -> re.Pattern[str]:
    return re.compile(pattern["source"], _A | (re.I if "i" in pattern["flags"] else 0))


@lru_cache(maxsize=1)
def _intent() -> dict[str, Any]:
    data = json.loads((Path(__file__).with_name("shared.json")).read_text(encoding="utf-8"))["intent"]
    return {
        "rules": [
            {
                "kind": rule["kind"],
                "trigger": _compile(rule["trigger"]),
                "allowed_by": _compile(rule["allowed_by"]) if rule.get("allowed_by") else None,
                "symmetric": bool(rule.get("symmetric")),
            }
            for rule in data["rules"]
        ],
        "negated_before": _compile(data["negated_before"]),
        "clause_break": _compile(data["clause_break"]),
        "negated_after": _compile(data["negated_after"]),
        "lookback": int(data["lookback"]),
    }


def _is_negated(text: str, index: int, length: int) -> bool:
    intent = _intent()
    before = text[max(0, index - intent["lookback"]):index]
    clause = intent["clause_break"].split(before)[-1]
    return bool(intent["negated_before"].search(clause) or intent["negated_after"].search(text[index + length:]))


def _occurrences(text: str, pattern: re.Pattern[str]) -> dict[str, str | None]:
    found: dict[str, str | None] = {"asked": None, "forbidden": None}
    for m in pattern.finditer(text):
        value = m.group(0).strip()
        if _is_negated(text, m.start(), len(m.group(0))):
            found["forbidden"] = found["forbidden"] or value
        else:
            found["asked"] = found["asked"] or value
        if found["asked"] and found["forbidden"]:
            break
    return found


def _rule_issue(rule: dict[str, Any], original: str, candidate: str) -> dict[str, str] | None:
    added = _occurrences(candidate, rule["trigger"])["asked"]
    if not rule["symmetric"]:
        if added and not _occurrences(original, rule["allowed_by"] or rule["trigger"])["asked"]:
            return {"kind": rule["kind"], "value": added}
        return None
    before = _occurrences(original, rule["trigger"])
    after = _occurrences(candidate, rule["trigger"])
    if bool(before["asked"]) != bool(after["asked"]):
        return {"kind": rule["kind"], "value": after["asked"] or before["asked"]}
    if bool(before["forbidden"]) != bool(after["forbidden"]):
        return {"kind": rule["kind"], "value": after["forbidden"] or before["forbidden"]}
    return None


def check_intent(original: str, candidate: str) -> list[dict[str, str]]:
    """What the candidate asks for that the draft did not (no chat context here)."""
    issues = (_rule_issue(rule, original, candidate) for rule in _intent()["rules"])
    return [issue for issue in issues if issue is not None]


def check_preservation(original: str, candidate: str) -> list[dict[str, str]]:
    """Issues as ``{"kind", "severity", "value"}``, in the TypeScript checker's order."""
    items, prose = _collect(original)
    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item["kind"], item["value"])
        if key in seen or _contains(candidate, item):
            continue
        seen.add(key)
        issues.append(dict(item))

    candidate_prose = _prose_of(candidate)
    for kind, pattern in (("negation", NEGATION_RE), ("requirement", REQUIREMENT_RE)):
        missing = len(pattern.findall(prose)) - len(pattern.findall(candidate_prose))
        if missing > 0:
            issues.append({"kind": kind, "severity": "review", "value": str(missing)})

    for issue in check_intent(original, candidate):
        issues.append({"kind": issue["kind"], "severity": "review", "value": issue["value"]})
    return issues
