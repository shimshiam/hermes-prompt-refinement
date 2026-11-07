# Prompt Refinement for Hermes Desktop

Review a deeper, expert version of your prompt before it is sent.

When you press Enter, a side model rewrites your draft into a stronger version of the same task. It keeps your goal, scope and deliverables, and keeps code, commands, paths, URLs, `@` references, names and numbers exactly as you wrote them. You approve it, edit it, send your original, or cancel. It ships **Off**.

| Mode | What happens on Enter |
|---|---|
| **Off** (default) | Your prompt is sent exactly as typed. |
| **Approval-First** | The draft is refined and a review drawer slides up out of the composer. **Nothing is sent until you choose**: Approve and send (⌘/Ctrl+Enter), Edit, Send original, or Cancel (your draft comes back). |
| **Automatic** | The draft is refined and sent with no click. It stops for you if refinement fails, if something exact went missing, or if the rewrite asks for an action your prompt didn't (deleting, installing, publishing, spending, credentials, …). |

Slash commands, queued, voice and hidden sends, and very short prompts are always sent as typed. The **Refine** pill beside the model picker switches mode, depth (Auto, Polish, Clarify, Deepen) and style in one click.

> **Status: preview.** Prompt Refinement needs the *composer review* additions to the Hermes Desktop plugin SDK, proposed upstream in SDK-PR-LINK. Until a Hermes release includes them, the plugin installs but stays inactive, and its settings page says what's missing. To try it now, see [Try it before release](#try-it-before-release).

## Install

Requires a Hermes Desktop release that includes the composer review SDK.

```bash
hermes plugins install shimshiam/hermes-prompt-refinement
```

Or in Hermes Desktop: **Skills ▸ Plugins ▸ Install from Git**. Pinning to a commit is recommended.

1. Answer **yes** to "Enable now?". That turns on the small Python half, which adds a *Prompt refinement* model slot under Settings ▸ Model ▸ Auxiliary. It's optional: without it, refinement uses your default auxiliary model.
2. In Desktop, open **Capabilities ▸ Plugins ▸ Prompt Refinement** and switch it on. A package's Desktop half is opt-in.
3. Open the composer's **Refine** pill and choose **Approval-First** to start.

Update with `hermes plugins update prompt-refinement`, remove with `hermes plugins remove prompt-refinement`. To stop it without removing it, set the Refine pill to **Off**.

## Try it before release

Until a release includes the SDK additions, developers can run Hermes from source with them applied. Use upstream's sandbox script, so your real `~/.hermes` and Desktop data aren't touched.

```bash
git clone https://github.com/shimshiam/hermes-agent.git
cd hermes-agent
git checkout feature/desktop-composer-review-sdk
# Install Hermes from source per its README and apps/desktop/BUILDING.md, then:
pnpm install
cd apps/desktop
../../scripts/dev-sandbox.sh --persistent -- pnpm run dev
```

Then install this plugin into that sandbox. In the sandboxed app, use **Skills ▸ Plugins ▸ Install from Git** with `https://github.com/shimshiam/hermes-prompt-refinement`, and follow steps 1–3 above.

## What it sends, and what it costs

- **One extra model call** for each refined send, through the model you chose: the Prompt refinement slot or this chat's model. Off sends nothing extra.
- The call is a stateless `llm.oneshot` request: no session, history, tools, skills or memory. It goes to the backend and profile that own the chat.
- It sends your draft text and **attachment names only**, never file contents. Chat context (the last few visible messages, at most 3,000 characters) is **off by default**, and the refiner is told to treat it as data.
- Settings are stored in Desktop plugin storage. The Python half adds `auxiliary.prompt_refinement` to `config.yaml` only if you pick a model there.

## Safety, and its limits

- **Fail closed:** the send middleware is registered `failClosed`. Any error, cancellation or failed refinement sends nothing, and your draft (text and attachments) goes back into the composer it came from. The composer is read-only while a send is refined.
- **Exact content:** Approve stays disabled while code, `@` references, URLs, paths, identifiers or numbers are missing from the rewrite.
- **No added actions:** the intent check flags a rewrite that asks for something your prompt didn't. Automatic stops; Approval-First asks you to confirm.

The checks are keyword and pattern rules over English text. They can't prove that meaning is preserved: a rewrite can widen a task in words no list anticipates. When intent matters, use **Approval-First** and read the rewrite. Details are in [docs/architecture.md](docs/architecture.md#limitations).

## Development

```bash
npm install
npm test               # pure-logic suites + SDK guard, standalone
npm run build          # src/ -> desktop/plugin.js (committed; installs run no build)
npm run check:build    # CI: desktop/plugin.js matches src/
```

The Desktop half is TypeScript/React in `src/`, built by esbuild into one ES module. Desktop lets a disk plugin import only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`. The Python half is `plugin.yaml` + `__init__.py`.

Tests that need a real Hermes checkout (the UI and real-composer suites, the Desktop typecheck, the Python test and the end-to-end runs) live in `scripts/test-in-hermes.sh`. It copies the plugin in, runs the suite and restores the checkout:

```bash
scripts/test-in-hermes.sh ../hermes-agent unit    # 230 tests, typecheck, Python test
scripts/test-in-hermes.sh ../hermes-agent e2e     # 9 scenarios: Off, Approval-First, Automatic
scripts/test-in-hermes.sh ../hermes-agent older   # on a Desktop without the SDK: stays inactive
```

How it works and where each guarantee lives: [docs/architecture.md](docs/architecture.md).

## License

MIT. See [LICENSE](LICENSE).
