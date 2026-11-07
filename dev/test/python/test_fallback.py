"""The stock-Hermes fallback (/refine-prompt, opt-in tool and skill), against a
recording fake of the plugin context: no Hermes needed. In-Hermes loading is
covered by test_prompt_refinement_plugin.py (scripts/test-in-hermes.sh unit)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from conftest import ROOT, load_module

plugin = load_module("__init__")
review = load_module("review")

DRAFT = "fix the flaky upload test in src/upload.test.ts and do not change any other files"
REVISED = "Fix the flaky upload test in src/upload.test.ts.\n\nConstraint: do not change any other files."


def answer(prompt=REVISED, **extra):
    return json.dumps({"prompt": prompt, "professional": "Reproduce it first.", **extra})


class FakeLlm:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.reply)


class FakeCtx:
    """Records every registration; anything else the plugin touches fails the test."""

    def __init__(self, settings=None, llm=None):
        self.settings = settings or {}
        self.llm = llm or FakeLlm(answer())
        self.aux, self.commands, self.tools, self.skills = [], {}, {}, {}

    def register_auxiliary_task(self, key, **kw):
        self.aux.append(key)

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_tool(self, name, toolset, schema, handler, description=""):
        self.tools[name] = (toolset, schema, handler)

    def register_skill(self, name, path, description=""):
        self.skills[name] = path

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def __getattr__(self, name):
        raise AssertionError(f"the plugin touched ctx.{name}")


def registered(**kw):
    ctx = FakeCtx(**kw)
    plugin.register(ctx)
    return ctx


# ── registration ───────────────────────────────────────────────────────────


def test_default_registers_the_slot_and_the_command_only():
    ctx = registered()
    assert ctx.aux == ["prompt_refinement"]
    assert list(ctx.commands) == ["refine-prompt"]
    assert ctx.tools == {} and ctx.skills == {}


def test_agent_tool_setting_adds_the_tool_and_the_skill():
    ctx = registered(settings={"agent_tool": True})
    assert list(ctx.tools) == ["refine_prompt"]
    assert ctx.tools["refine_prompt"][0] == "prompt_refinement"
    assert ctx.skills["refine-prompt"].is_file()


@pytest.mark.parametrize("value", ["true", 1, "yes"])
def test_only_a_real_true_turns_the_tool_on(value):
    assert registered(settings={"agent_tool": value}).tools == {}


def test_command_name_is_not_a_hermes_builtin():
    assert review.COMMAND not in {"refine", "review", "prompt"}


# ── /refine-prompt ─────────────────────────────────────────────────────────


def run(raw, llm=None):
    ctx = registered(llm=llm)
    return ctx.commands["refine-prompt"](raw), ctx.llm


def test_shows_both_prompts_and_sends_nothing_to_the_agent():
    out, llm = run(DRAFT)
    assert "nothing was sent to the agent" in out
    assert DRAFT in out and REVISED in out
    assert out.index("**Your prompt**") < out.index("**Revised prompt**")
    assert "✓ Every exact item" in out
    assert "What a professional would add: Reproduce it first." in out
    assert len(llm.calls) == 1


def test_one_stateless_call_through_the_plugin_slot_with_the_desktop_instructions():
    _, llm = run(DRAFT)
    call = llm.calls[0]
    assert call["task"] == "prompt_refinement"
    system, user = call["messages"]
    assert system["role"] == "system" and system["content"] == review.shared()["calls"]["auto"]["auto"]["instructions"]
    assert "You never perform the task yourself" in system["content"]
    assert user == {"role": "user", "content": f"<draft_prompt>\n{DRAFT}\n</draft_prompt>"}
    assert set(call) == {"messages", "task", "max_tokens", "temperature", "timeout", "purpose"}


def test_depth_and_style_flags():
    out, llm = run(f"--depth polish --style technical {DRAFT}")
    assert llm.calls[0]["messages"][0]["content"] == review.shared()["calls"]["polish"]["technical"]["instructions"]
    assert "depth Polish" in out
    out, _ = run(f"--depth=clarify {DRAFT}")
    assert "depth Clarify" in out


def test_auto_depth_reports_what_the_model_chose():
    out, _ = run(DRAFT, FakeLlm(answer(depth="deepen")))
    assert "depth Auto → Deepen" in out


def test_usage_and_bad_flags_make_no_model_call():
    for raw in ("", "   ", "--depth deepen"):
        out, llm = run(raw)
        assert out.startswith("Usage: /refine-prompt") and llm.calls == []
    out, llm = run("--depth huge fix it")
    assert "Unknown --depth 'huge'" in out and llm.calls == []


def test_flags_a_dropped_path_and_an_added_delete():
    out, _ = run(DRAFT, FakeLlm(answer("Fix the flaky upload test and delete the old fixtures.")))
    assert "⚠ Missing from the revised prompt (exact items): path “src/upload.test.ts”" in out
    assert "⚠ The revision asks for more than your prompt did: deleting or overwriting “delete”" in out


def test_failures_say_so_and_never_raise():
    out, _ = run(DRAFT, FakeLlm(error=RuntimeError("no provider configured")))
    assert "The model call failed" in out and "no provider configured" in out
    out, _ = run(DRAFT, FakeLlm('{"prompt": '))
    assert "couldn't be read" in out
    out, llm = run("x" * (review.shared()["max_chars"] + 1))
    assert "too long" in out and llm.calls == []


def test_a_plain_text_answer_is_accepted_and_fences_never_break():
    tricky = "Explain this:\n```js\nconsole.log(1)\n```"
    out, _ = run(tricky, FakeLlm("Explain what this snippet prints:\n```js\nconsole.log(1)\n```"))
    assert "````text" in out
    assert out.count("````") == 4


# ── opt-in tool ────────────────────────────────────────────────────────────


def test_tool_returns_both_prompts_and_tells_the_agent_to_stop():
    ctx = registered(settings={"agent_tool": True})
    handler = ctx.tools["refine_prompt"][2]
    payload = json.loads(handler({"prompt": DRAFT, "depth": "nonsense"}, task_id="t1"))
    assert payload["original"] == DRAFT and payload["revised"] == REVISED
    assert payload["depth"] == "auto"
    assert "Do not perform the task" in payload["next_step"]
    assert len(ctx.llm.calls) == 1


def test_tool_failure_is_an_error_payload_not_an_exception():
    ctx = registered(settings={"agent_tool": True}, llm=FakeLlm(error=TimeoutError("slow")))
    payload = json.loads(ctx.tools["refine_prompt"][2]({"prompt": DRAFT}))
    assert "error" in payload and "Do not perform the task" in payload["next_step"]


def test_tool_description_limits_when_it_may_be_called():
    description = review.TOOL_SCHEMA["description"]
    assert "only when the user explicitly asks" in description
    assert "do not carry out the task" in description


def test_skill_tells_the_agent_to_stop_after_showing_the_review():
    text = (ROOT / "skills/refine-prompt/SKILL.md").read_text(encoding="utf-8")
    assert "**Stop there.**" in text and "/refine-prompt" in text
