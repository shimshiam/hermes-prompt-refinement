# Prompt Refinement for Hermes

Review a deeper, expert version of your prompt before it is sent.

A side model rewrites your draft into a stronger version of the same task. It keeps your goal, scope and deliverables, and keeps code, commands, paths, URLs, `@` references, names and numbers exactly as you wrote them. Then you decide what to send.

## Choose your setup

There are two ways to use this repository. They differ in what you get, and in whether your existing Hermes is touched.

| | **1. Full Desktop feature** (preview) | **2. Fallback in your existing Hermes** |
|---|---|---|
| What you get | Refinement **on Enter** in Hermes Desktop: **Off**, **Approval-First** (a review drawer; nothing is sent until you approve) and **Automatic** (refines and sends, but stops for review on any problem) | A **`/refine-prompt <prompt>`** command that shows your prompt beside a revised version. You copy the one you want and send it yourself. |
| Where | Hermes Desktop only | CLI, TUI, Desktop, and messaging platforms (Telegram shows it as `/refine_prompt`) |
| Your existing Hermes | **Not touched.** It runs in a separate, isolated development build. | **Installs into it**, like any Git plugin. Off until you enable it, and removable. |
| Needs | Building Hermes from source (developer comfort). The Desktop SDK additions it needs are proposed in [NousResearch/hermes-agent#150772](https://github.com/NousResearch/hermes-agent/pull/150772) and aren't released yet. | Any recent Hermes with plugin support |

The fallback is **not** the Desktop feature in a different place. It has no review drawer, no Automatic mode, and nothing that intercepts or holds your sends. It's a command you run on purpose.

### Asking an agent to install it

If you give this repository to an AI agent to install, send this prompt with the link, so it asks you before choosing:

```text
Install the Hermes plugin at https://github.com/shimshiam/hermes-prompt-refinement.
First read the "Choose your setup" section of its README, explain the two setups to me in a few sentences, and ask me which one I want. Don't install or change anything until I answer. If I choose the full Desktop feature, keep it entirely separate from my existing Hermes.
```

**For agents reading this:** if a user asks you to install this repository and hasn't said which setup they want, don't choose for them. Explain both setups above in plain words, including what each changes on their machine, and ask. Then follow only the section they choose. This README can't force an agent to do that, which is why the prompt above asks for it explicitly.

## Setup 1: the full Desktop feature (isolated development build)

**What it is:** Hermes Desktop built from source with the SDK additions from [#150772](https://github.com/NousResearch/hermes-agent/pull/150772), with this plugin installed inside a sandbox.
- The sandbox has its own Hermes home, its own Desktop data and its own app name, so your existing Hermes (its config, chats, sign-ins and data) is never touched.
- You set up a model provider inside the sandbox, the same way you did for your main Hermes.

```bash
git clone https://github.com/shimshiam/hermes-agent.git
cd hermes-agent
git checkout feature/desktop-composer-review-sdk
# Install Hermes from source per the repo's README and apps/desktop/BUILDING.md, then:
pnpm install
cd apps/desktop
../../scripts/dev-sandbox.sh --persistent -- hermes plugins install shimshiam/hermes-prompt-refinement --enable
../../scripts/dev-sandbox.sh --persistent -- pnpm run dev
```

In the sandboxed app:
1. Open **Capabilities ▸ Plugins ▸ Prompt Refinement** and switch it on. A package's Desktop half is opt-in.
2. Open the composer's **Refine** pill and choose **Approval-First** to start.

| Mode | What happens on Enter |
|---|---|
| **Off** (default) | Your prompt is sent exactly as typed. |
| **Approval-First** | The draft is refined and a review drawer slides up out of the composer. **Nothing is sent until you choose**: Approve and send (⌘/Ctrl+Enter), Edit, Send original, or Cancel (your draft comes back). |
| **Automatic** | The draft is refined and sent with no click. It stops for you if refinement fails, if something exact went missing, or if the rewrite asks for an action your prompt didn't (deleting, installing, publishing, spending, credentials, …). |

- Slash commands, queued, voice and hidden sends, and very short prompts are always sent as typed.
- The **Refine** pill also sets depth (Auto, Polish, Clarify, Deepen) and style.
- `/refine-prompt` works in this build too.

**When the SDK additions ship in a Hermes release**, you won't need the source build. Install the plugin into your normal Hermes as in Setup 2, switch on its Desktop half (step 1 above), and pick a mode.

**Status: preview.** On a Hermes Desktop without the SDK additions, the Desktop half installs but stays inactive. It registers nothing that touches your sends, and its settings page says what's missing.

## Setup 2: the fallback in your existing Hermes

```bash
hermes plugins install shimshiam/hermes-prompt-refinement --enable
hermes gateway restart
```

Or in Hermes Desktop: **Skills ▸ Plugins ▸ Install from Git**, then restart Hermes. Pinning to a commit is recommended: `--ref <full commit SHA>`.

Then, in any chat:

```text
/refine-prompt fix the flaky upload test in src/upload.test.ts and don't change any other files
```

You get back:
- **Your prompt** and the **revised prompt**, each in a code block you can copy;
- the depth it chose, and what was added and why;
- a **Check** section: anything exact (paths, code, URLs, `@` references, names, numbers) that went missing, anything the revision asks for that your prompt didn't (deleting, installing, publishing, spending, credentials, delegation), and any softened negations or requirements.

Nothing is sent to the agent. You send the version you want yourself.

Options: `--depth auto|polish|clarify|deepen` and `--style auto|clarity|technical|research|creative|agentic`. For example, `/refine-prompt --depth polish <prompt>` fixes wording only.

**Model:** it uses your configured model. To use a different one for refinement, pick it under **Prompt refinement** in Settings ▸ Model ▸ Auxiliary (or `hermes model` ▸ auxiliary models).

**Optional: let the agent do it on request.** This is off by default, because a tool sits in every conversation's tool list.

```bash
hermes config set plugins.entries.prompt-refinement.settings.agent_tool true
hermes gateway restart
```

That adds a `refine_prompt` tool and a `prompt-refinement:refine-prompt` skill. When you ask in plain words ("review this prompt: …"), the agent calls the tool, shows you both versions and stops. The tool never performs the task. The instruction to stop afterwards is a model instruction, so `/refine-prompt` is the dependable way.

**What the fallback doesn't have:**
- No review drawer, no Enter trigger, no Approval-First gate and no Automatic mode. Nothing watches or holds your sends.
- No opt-in chat context: it refines only the text you give it.
- In Hermes Desktop on a release without the SDK additions, the Desktop half stays inactive (see Setup 1), and `/refine-prompt` is what works.

Remove with `hermes plugins remove prompt-refinement`. Update with `hermes plugins update prompt-refinement`.

## What it sends, and what it costs

- **One extra model call** each time it refines a prompt (an Approval-First or Automatic send, or one `/refine-prompt`), through your configured model or the one you picked for the Prompt refinement slot. Off sends nothing extra.
- The call is stateless: no session, history, tools, skills or memory.
- It sends the prompt text, and in Desktop **attachment names only**, never file contents. Desktop's chat context (the last few visible messages, at most 3,000 characters) is **off by default**, and the refiner is told to treat it as data.
- Desktop settings are stored in Desktop plugin storage. Hermes config is touched only if you pick a refinement model (`auxiliary.prompt_refinement`) or turn on the agent tool.

## Safety, and its limits

- **Never starts the task:** refinement is a separate model call told never to perform the task. `/refine-prompt` is a command, not an agent turn.
- **Fail closed (Desktop):** the send middleware is registered `failClosed`. Any error, cancellation or failed refinement sends nothing, and your draft (text and attachments) goes back into the composer it came from. The composer is read-only while a send is refined.
- **Exact content:** Desktop keeps Approve disabled, and `/refine-prompt` warns, while code, `@` references, URLs, paths, identifiers or numbers are missing from the rewrite.
- **No added actions:** the intent check flags a rewrite that asks for something your prompt didn't. Automatic stops; Approval-First asks you to confirm; `/refine-prompt` warns.

The checks are keyword and pattern rules over English text. They can't prove that meaning is preserved: a rewrite can widen a task in words no list anticipates. Read the rewrite before you send it. Details are in [docs/architecture.md](docs/architecture.md#limitations).

## Development

Development lives in `dev/`. The repository root holds only what an install needs.

```bash
cd dev
npm install
npm test               # Desktop half: logic suites + SDK guard, standalone
pytest                 # fallback: /refine-prompt, tool, parity with the TypeScript checks
npm run build          # dev/src -> desktop/plugin.js, shared.json, dev/test/parity/expected.json (committed)
npm run check:build    # CI: the committed build outputs match dev/src
```

**Layout:**
- **Desktop half:** TypeScript/React in `dev/src/`, built by esbuild into one ES module (Desktop lets a disk plugin import only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`).
- **Python half:** `plugin.yaml`, `__init__.py`, `review.py` (`/refine-prompt` and the tool), `checks.py` and `skills/`.
- **Shared source:** both halves use the same refinement instructions and intent rules, exported from `dev/src` into `shared.json`. A parity test holds `checks.py` to the TypeScript checker's verdicts.

Tests that need a real Hermes checkout live in `dev/scripts/test-in-hermes.sh`: the UI and real-composer suites, the Desktop typecheck, the Python half loaded by Hermes, and the end-to-end runs. It copies the plugin in, runs the suite and restores the checkout:

```bash
dev/scripts/test-in-hermes.sh ../hermes-agent unit    # 230 tests, typecheck, Python half in Hermes
dev/scripts/test-in-hermes.sh ../hermes-agent e2e     # 9 scenarios: Off, Approval-First, Automatic
dev/scripts/test-in-hermes.sh ../hermes-agent older   # on a Desktop without the SDK: stays inactive
```

How it works and where each guarantee lives: [docs/architecture.md](docs/architecture.md).

## License

MIT. See [LICENSE](LICENSE).
