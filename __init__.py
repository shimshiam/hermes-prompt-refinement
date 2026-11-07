"""Prompt Refinement: the Hermes (Python) half.

Always:
- registers the ``prompt_refinement`` auxiliary model slot (Settings > Model >
  Auxiliary), which the Desktop half (``desktop/plugin.js``, built from
  ``dev/src``) and the fallback
  below call through. Until the user picks a model there, it follows the
  default auxiliary route.
- registers ``/refine-prompt``, the stock-Hermes fallback: it returns the
  original and a revised prompt for the user to review. It is a slash command,
  not an agent turn, so it never starts the task the prompt describes. It works
  in the CLI, TUI, Desktop and messaging platforms on any Hermes with plugin
  slash commands; it is not the Desktop review drawer and has no Automatic mode.

Opt-in (``plugins.entries.prompt-refinement.settings.agent_tool: true``):
- a ``refine_prompt`` tool and the ``prompt-refinement:refine-prompt`` skill,
  so the agent can review a prompt when the user asks in plain words. Off by
  default: a tool sits in every conversation's tool list.
"""

from __future__ import annotations

from pathlib import Path

TASK_KEY = "prompt_refinement"


def register(ctx) -> None:
    # Imported here, not at module level: this file is also the repository root,
    # and test runners import it without its package.
    from .review import COMMAND, TOOL, TOOL_SCHEMA, make_command, make_tool

    ctx.register_auxiliary_task(
        TASK_KEY,
        display_name="Prompt refinement",
        description="Rewrites a draft prompt for review before you send it (Desktop review, /refine-prompt).",
    )

    llm_of = lambda: ctx.llm  # noqa: E731  resolved per call: the host owns credentials and routing

    ctx.register_command(
        COMMAND,
        handler=make_command(llm_of),
        description="Review a prompt: show it beside a revised version. Sends nothing to the agent.",
        args_hint="<prompt>",
    )

    if ctx.get_config("agent_tool", default=False) is True:
        ctx.register_tool(
            name=TOOL,
            toolset="prompt_refinement",
            schema=TOOL_SCHEMA,
            handler=make_tool(llm_of),
            description=TOOL_SCHEMA["description"],
        )
        ctx.register_skill(
            "refine-prompt",
            Path(__file__).parent / "skills" / "refine-prompt" / "SKILL.md",
            description="Review or improve a prompt the user wants to send, without carrying out its task.",
        )
