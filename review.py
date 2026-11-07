"""The stock-Hermes fallback: review a prompt without sending it.

``/refine-prompt <prompt>`` asks the user's configured model (the plugin's
``prompt_refinement`` auxiliary slot, which follows the main model until the
user picks one) for a revised prompt and returns the original and the revision
for the user to read. It is a slash command, not an agent turn: nothing here
reaches the agent, runs a tool, or starts the task the prompt describes.

The refinement instructions are the Desktop plugin's own (``shared.json``,
exported from ``dev/src/prompt.ts`` by ``dev/build.mjs``), and the checks are the same
rules (``checks.py``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

from .checks import check_preservation

TASK = "prompt_refinement"
COMMAND = "refine-prompt"
TOOL = "refine_prompt"
DEPTH_NAMES = {"auto": "Auto", "polish": "Polish", "clarify": "Clarify", "deepen": "Deepen"}
TIMEOUT_S = 90.0

USAGE = (
    "Usage: /refine-prompt [--depth auto|polish|clarify|deepen] [--style auto|clarity|technical|research|creative|agentic] <prompt>\n\n"
    "Shows your prompt and a revised version side by side. Nothing is sent to the agent; "
    "copy the version you want and send it yourself."
)

KIND_LABELS = {
    "code-block": "code block",
    "inline-code": "inline code",
    "reference": "@ reference",
    "url": "URL",
    "path": "path",
    "identifier": "identifier",
    "number": "number",
    "name": "name",
    "negation": "negation words (not, never, without…)",
    "requirement": "requirement words (must, only, exactly…)",
    "destructive": "deleting or overwriting",
    "file-change": "changing files",
    "install": "installing software",
    "external": "contacting someone or publishing",
    "spending": "spending money",
    "permission": "permissions or credentials",
    "delegation": "delegation (subagents, swarms)",
}
INTENT_KINDS = {"destructive", "file-change", "install", "external", "spending", "permission", "delegation"}


@lru_cache(maxsize=1)
def shared() -> dict[str, Any]:
    return json.loads(Path(__file__).with_name("shared.json").read_text(encoding="utf-8"))


class ReviewError(Exception):
    """A review that could not produce a revised prompt. The message is user-facing."""


@dataclass
class Review:
    original: str
    revised: str
    depth: str
    chosen_depth: Optional[str] = None
    analysis: dict[str, str] = field(default_factory=dict)
    issues: list[dict[str, str]] = field(default_factory=list)

    @property
    def missing(self) -> list[dict[str, str]]:
        return [i for i in self.issues if i["severity"] == "blocking"]

    @property
    def added_actions(self) -> list[dict[str, str]]:
        return [i for i in self.issues if i["kind"] in INTENT_KINDS]

    @property
    def softened(self) -> list[dict[str, str]]:
        return [i for i in self.issues if i["severity"] == "review" and i["kind"] not in INTENT_KINDS]

    def as_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "revised": self.revised,
            "depth": self.chosen_depth or self.depth,
            "what_was_added": self.analysis,
            "missing_from_revision": [{"kind": i["kind"], "value": i["value"]} for i in self.missing],
            "asks_for_more_than_the_prompt": [{"kind": i["kind"], "value": i["value"]} for i in self.added_actions],
            "check_wording": [{"kind": i["kind"], "value": i["value"]} for i in self.softened],
        }


# ── arguments ──────────────────────────────────────────────────────────────

_FLAG_RE = re.compile(r"^\s*--(depth|style)(?:=|\s+)([A-Za-z]+)")


def parse_args(raw: str) -> tuple[str, str, str]:
    """``(prompt, depth, style)`` from ``[--depth X] [--style Y] <prompt>``. ValueError on a bad flag."""
    text = raw or ""
    depth, style = "auto", "auto"
    while True:
        m = _FLAG_RE.match(text)
        if not m:
            break
        name, value = m.group(1), m.group(2).lower()
        allowed = shared()["depths"] if name == "depth" else shared()["styles"]
        if value not in allowed:
            raise ValueError(f"Unknown --{name} '{value}'. Choose one of: {', '.join(allowed)}.")
        if name == "depth":
            depth = value
        else:
            style = value
        text = text[m.end():]
    return text.strip(), depth, style


# ── the model call ─────────────────────────────────────────────────────────


def build_messages(prompt: str, depth: str, style: str) -> tuple[list[dict[str, str]], int, float]:
    call = shared()["calls"][depth][style]
    user = shared()["input_template"].replace("{draft}", prompt)
    return (
        [{"role": "system", "content": call["instructions"]}, {"role": "user", "content": user}],
        int(call["max_tokens"]),
        float(call["temperature"]),
    )


def _line(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def parse_answer(raw: str) -> Optional[dict[str, Any]]:
    """Port of ``parseRefinement`` (src/prompt.ts): JSON answer, or a plain-text prompt; None if unreadable."""
    text = re.sub(r"^```(?:json)?\s*\n?([\s\S]*?)\n?```$", r"\1", (raw or "").strip(), flags=re.I).strip()
    if not text:
        return None
    if not (text.startswith("{") or re.match(r"^\{?\s*\"prompt\"\s*:", text)):
        return {"prompt": text, "analysis": {}, "depth": None}
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict) or not _line(obj.get("prompt")):
        return None
    analysis = {
        "professional": _line(obj.get("professional")),
        "raw_material": _line(obj.get("raw_material")),
        "methods": _line(obj.get("methods")),
        "verification": _line(obj.get("verification")),
    }
    depth = _line(obj.get("depth")).lower()
    return {
        "prompt": _line(obj.get("prompt")),
        "analysis": {k: v for k, v in analysis.items() if v},
        "depth": depth if depth in ("polish", "clarify", "deepen") else None,
    }


def run_review(llm: Any, prompt: str, depth: str = "auto", style: str = "auto") -> Review:
    """One stateless model call through ``ctx.llm``. Raises ReviewError with a user-facing message."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ReviewError(USAGE)
    if len(prompt) > shared()["max_chars"]:
        raise ReviewError(f"This prompt is too long to review (over {shared()['max_chars']:,} characters).")
    messages, max_tokens, temperature = build_messages(prompt, depth, style)
    try:
        result = llm.complete(
            messages=messages,
            task=TASK,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=TIMEOUT_S,
            purpose="prompt-refinement.review",
        )
    except Exception as exc:  # provider errors, trust gate, timeouts
        raise ReviewError(f"The model call failed, so there is no revised prompt: {exc}") from exc
    parsed = parse_answer(getattr(result, "text", "") or "")
    if parsed is None:
        raise ReviewError("The model answered in a form that couldn't be read. Try again.")
    return Review(
        original=prompt,
        revised=parsed["prompt"],
        depth=depth,
        chosen_depth=parsed["depth"],
        analysis=parsed["analysis"],
        issues=check_preservation(prompt, parsed["prompt"]),
    )


# ── presentation ───────────────────────────────────────────────────────────


def _fence(text: str) -> str:
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return f"{ticks}text\n{text}\n{ticks}"


def _items(issues: list[dict[str, str]]) -> str:
    return "; ".join(f"{KIND_LABELS.get(i['kind'], i['kind'])} “{i['value']}”" for i in issues)


def format_review(review: Review) -> str:
    depth = DEPTH_NAMES.get(review.chosen_depth or review.depth, review.depth)
    if review.depth == "auto" and review.chosen_depth:
        depth = f"Auto → {DEPTH_NAMES[review.chosen_depth]}"
    parts = [
        f"**Prompt review** · depth {depth} · nothing was sent to the agent",
        "**Your prompt**",
        _fence(review.original),
        "**Revised prompt**",
        _fence(review.revised),
    ]
    if review.analysis:
        labels = {
            "professional": "What a professional would add",
            "raw_material": "Start from",
            "methods": "Methods",
            "verification": "Verify with",
        }
        parts.append("**What was added and why**\n" + "\n".join(f"- {labels[k]}: {v}" for k, v in review.analysis.items()))
    checks: list[str] = []
    if review.missing:
        checks.append(f"⚠ Missing from the revised prompt (exact items): {_items(review.missing)}. Use your original, or edit the revision.")
    if review.added_actions:
        checks.append(f"⚠ The revision asks for more than your prompt did: {_items(review.added_actions)}.")
    if review.softened:
        checks.append(f"Check the wording: fewer {_items(review.softened)} than your prompt.")
    if not checks:
        checks.append("✓ Every exact item (code, paths, URLs, @ references, names, numbers) is kept, and nothing new is asked for.")
    parts.append("**Check**\n" + "\n".join(f"- {c}" for c in checks))
    parts.append("Copy the version you want and send it yourself. These checks are keyword rules; read the revision before you send it.")
    return "\n\n".join(parts)


# ── entry points ───────────────────────────────────────────────────────────


def make_command(llm_of: Callable[[], Any]) -> Callable[..., str]:
    """``/refine-prompt`` handler: returns text to show; never starts an agent turn."""

    def handle(raw_args: str) -> str:
        try:
            prompt, depth, style = parse_args(raw_args)
        except ValueError as exc:
            return f"{exc}\n\n{USAGE}"
        if not prompt:
            return USAGE
        try:
            return format_review(run_review(llm_of(), prompt, depth, style))
        except ReviewError as exc:
            return f"**Prompt review** · nothing was sent to the agent\n\n{exc}"

    return handle


TOOL_SCHEMA = {
    "name": TOOL,
    "description": (
        "Review a prompt the user wants to improve BEFORE it is used: returns the original and a revised version "
        "for the user to read. Call it only when the user explicitly asks to review, refine, rewrite or improve "
        "a prompt. Never call it on the user's own request before acting on that request. After it returns, show "
        "the user both versions and stop: do not carry out the task the prompt describes, in this turn or later, "
        "unless the user sends the prompt as a new request."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The prompt to review, exactly as the user wrote it."},
            "depth": {
                "type": "string",
                "enum": ["auto", "polish", "clarify", "deepen"],
                "description": "How far to go. Default auto.",
            },
        },
        "required": ["prompt"],
    },
}


def make_tool(llm_of: Callable[[], Any]) -> Callable[..., str]:
    """``refine_prompt`` tool handler (opt-in). Returns JSON; the task itself is never performed."""

    def handle(args: dict, **_: Any) -> str:
        prompt = str((args or {}).get("prompt") or "")
        depth = str((args or {}).get("depth") or "auto").lower()
        if depth not in shared()["depths"]:
            depth = "auto"
        try:
            review = run_review(llm_of(), prompt, depth)
        except ReviewError as exc:
            return json.dumps({"error": str(exc), "next_step": "Tell the user the review failed. Do not perform the task."})
        payload = review.as_dict()
        payload["next_step"] = (
            "Show the user both prompts and any check findings, then stop. Do not perform the task; "
            "the user decides whether to send the original or the revision."
        )
        return json.dumps(payload, ensure_ascii=False)

    return handle
