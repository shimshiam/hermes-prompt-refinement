---
name: refine-prompt
description: Review or improve a prompt the user wants to send, without carrying out its task.
---

# Prompt review

Use this when the user explicitly asks you to review, refine, rewrite or improve a prompt (theirs, or one they are drafting for an agent), not when they simply ask you to do something.

1. Call the `refine_prompt` tool with the prompt exactly as the user wrote it. Pass `depth` only if the user asked for one: `polish` (wording only), `clarify` (spell out what is implied), or `deepen` (a professional's version of the same task). Otherwise omit it.
2. Show the user:
   - their prompt and the revised prompt, each in its own code block;
   - "What was added and why", if present;
   - every finding under `missing_from_revision`, `asks_for_more_than_the_prompt` and `check_wording`, in plain words.
3. **Stop there.** Do not carry out the task the prompt describes, do not start planning it, and do not call other tools for it. The user decides what to send. If they then ask you to proceed, treat the prompt they choose as a new request.

If the tool returns an `error`, tell the user the review failed and still do not perform the task.

The user can do the same thing without you: `/refine-prompt <prompt>` shows the review directly and never reaches the agent.
