# Changelog

## Unreleased

- New: `/refine-prompt`, a fallback for any Hermes. It shows your prompt beside a revised version and sends nothing to the agent. Optional `refine_prompt` tool and skill (`agent_tool` setting, off by default).
- README: "Choose your setup" (the full Desktop feature in an isolated build, or the fallback in your existing Hermes), with a prompt to give an agent.
- Repository layout: development moved to `dev/`; the root holds only what an install needs, so installing no longer offers Node dependencies.
- The intent rules are exported for the fallback (`shared.json`); the install scanner no longer flags a comment in them.

## 0.1.0 (preview)

- First standalone release of Prompt Refinement for Hermes Desktop, moved out of the Hermes tree (NousResearch/hermes-agent#149911) into its own package. Needs the composer review SDK from [NousResearch/hermes-agent#150772](https://github.com/NousResearch/hermes-agent/pull/150772).
- Off, Approval-First and Automatic modes; Auto / Polish / Clarify / Deepen depth; styles; opt-in chat context.
- Fail-closed send gate, exact-content preservation check, intent check.
- New: on a Hermes Desktop without the composer review SDK the plugin stays inactive and its settings page says what is missing.
