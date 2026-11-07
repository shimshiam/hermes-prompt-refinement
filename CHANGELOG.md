# Changelog

## 0.1.0 (preview)

- First standalone release of Prompt Refinement for Hermes Desktop, moved out of the Hermes tree (NousResearch/hermes-agent#149911) into its own package. Needs the composer review SDK from [NousResearch/hermes-agent#150772](https://github.com/NousResearch/hermes-agent/pull/150772).
- Off, Approval-First and Automatic modes; Auto / Polish / Clarify / Deepen depth; styles; opt-in chat context.
- Fail-closed send gate, exact-content preservation check, intent check.
- New: on a Hermes Desktop without the composer review SDK the plugin stays inactive and its settings page says what is missing.
