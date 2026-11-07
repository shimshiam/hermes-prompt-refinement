"""The bundled ``prompt-refinement`` plugin gives Desktop's refinement call a selectable model slot.

Loads the real in-tree plugin through ``PluginManager`` discovery against temp homes (no fake
registry): enabled, the ``prompt_refinement`` slot is listed on the Settings > Model surface and a
pin there is what ``call_llm(task="prompt_refinement")`` resolves; not enabled (the default), the
slot does not exist and the same task falls back to the automatic route instead of failing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import hermes_cli.plugins as plugins_mod
from agent.auxiliary_client import _get_auxiliary_task_config
from hermes_cli.plugins import PluginManager
from hermes_cli.web_server_config import _apply_model_assignment_sync, _aux_task_slots
from hermes_cli.web_server_profiles import _profile_scope
from hermes_cli.web_routers.models import get_auxiliary_models

TASK = "prompt_refinement"


def _write_home(home: Path, *, enabled: bool) -> None:
    home.mkdir(parents=True)
    # JSON is valid YAML; keeps the test free of a yaml dependency.
    (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["prompt-refinement"] if enabled else []}}))


@pytest.fixture
def homes(tmp_path, monkeypatch):
    """Process home ``a`` enables the plugin; named profile ``b`` does not."""
    home_a = tmp_path / ".hermes"
    home_b = home_a / "profiles" / "b"
    _write_home(home_a, enabled=True)
    _write_home(home_b, enabled=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home_a))
    monkeypatch.delenv("HERMES_BUNDLED_PLUGINS", raising=False)
    monkeypatch.setattr(PluginManager, "_scan_entry_points", lambda self: [])
    plugins_mod._reset_plugin_managers_for_tests()
    yield home_a, home_b
    plugins_mod._reset_plugin_managers_for_tests()


def _row(profile):
    return {row["task"]: row for row in get_auxiliary_models(profile=profile)["tasks"]}.get(TASK)


def test_enabled_plugin_lists_the_slot_with_its_own_copy(homes):
    row = _row(None)
    assert row is not None
    assert (row["label"], row["plugin"]) == ("Prompt refinement", "prompt-refinement")
    assert row["provider"] == "auto"
    with _profile_scope(None):
        assert TASK in _aux_task_slots()


def test_slot_is_absent_where_the_plugin_is_not_enabled(homes):
    assert _row("b") is None
    with _profile_scope("b"):
        assert TASK not in _aux_task_slots()
        # The Desktop call still resolves: an unknown task has no pin, so the auto route applies.
        assert _get_auxiliary_task_config(TASK) == {}


def test_pin_is_per_profile_and_is_what_the_refinement_call_resolves(homes):
    home_a, home_b = homes
    with _profile_scope(None):
        _apply_model_assignment_sync("auxiliary", "openrouter", "vendor/refiner", TASK, "", "")
        assert _get_auxiliary_task_config(TASK).get("model") == "vendor/refiner"
    assert TASK in (home_a / "config.yaml").read_text()
    assert TASK not in (home_b / "config.yaml").read_text()


# ── the stock-Hermes fallback, loaded by Hermes itself ─────────────────────


def _fake_provider(monkeypatch, content):
    """Replace only the provider call under ctx.llm: Hermes's own trust gate and routing still run."""
    import agent.auxiliary_client as aux
    from types import SimpleNamespace

    calls = []

    def call_llm(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content=content, reasoning=None, reasoning_content=None, tool_calls=None)
        choice = SimpleNamespace(message=message, finish_reason="stop", index=0)
        return SimpleNamespace(choices=[choice], usage=None, model="fake-model")

    monkeypatch.setattr(aux, "call_llm", call_llm)
    return calls


def test_enabled_plugin_registers_refine_prompt_and_no_tool_by_default(homes):
    from hermes_cli.plugins import get_plugin_commands, get_plugin_manager

    assert "refine-prompt" in get_plugin_commands()
    manager = get_plugin_manager()
    assert "refine_prompt" not in manager._plugin_tool_names
    assert "prompt-refinement:refine-prompt" not in manager._plugin_skills


def test_refine_prompt_answers_through_the_plugin_slot_and_never_reaches_the_agent(homes, monkeypatch):
    from hermes_cli.plugins import get_plugin_command_handler

    calls = _fake_provider(monkeypatch, json.dumps({"prompt": "Fix the flaky test in src/upload.test.ts."}))
    out = get_plugin_command_handler("refine-prompt")("fix the flaky test in src/upload.test.ts")

    assert "nothing was sent to the agent" in out
    assert "Fix the flaky test in src/upload.test.ts." in out
    assert len(calls) == 1 and calls[0]["task"] == TASK
    assert calls[0]["messages"][0]["role"] == "system"


def test_agent_tool_setting_registers_the_tool_and_the_skill(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(json.dumps({
        "plugins": {
            "enabled": ["prompt-refinement"],
            "entries": {"prompt-refinement": {"settings": {"agent_tool": True}}},
        }
    }))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_BUNDLED_PLUGINS", raising=False)
    monkeypatch.setattr(PluginManager, "_scan_entry_points", lambda self: [])
    plugins_mod._reset_plugin_managers_for_tests()
    try:
        from hermes_cli.plugins import get_plugin_manager, _ensure_plugins_discovered

        _ensure_plugins_discovered()
        manager = get_plugin_manager()
        assert "refine_prompt" in manager._plugin_tool_names
        assert "prompt-refinement:refine-prompt" in manager._plugin_skills
    finally:
        plugins_mod._reset_plugin_managers_for_tests()
