/**
 * Prompt Refinement on a Hermes Desktop WITHOUT the composer review SDK (an
 * older release): installed and switched on, it must stay inactive, say why on
 * its settings page, and leave every send untouched.
 *
 * Otherwise identical setup to prompt-refinement.spec.ts: the real Desktop app, a real gateway built
 * from this checkout, and the real `llm.oneshot` path to a mock OpenAI-
 * compatible model — all inside a throwaway sandbox (temp HOME, HERMES_HOME
 * and Electron userData; see fixtures.ts).
 *
 * The mock answers the refinement request (its input carries `<draft_prompt>`)
 * with a structured rewrite, and every agent turn with a fixed reply.
 * `receivedPrompts` is the witness of what the agent actually received:
 *  - Automatic sends a clean refinement with no click, and never the draft;
 *  - it stops (sends nothing) when the refinement would drop something, or
 *    asks for an action the prompt did not (a delete);
 *  - Cancel sends nothing; Approval-First opens the review on Enter and sends nothing
 *    until the user approves (or sends the original), and a failed refinement
 *    sends nothing whatever is pressed.
 *
 * Installed as a package, the way `hermes plugins install` lands it: the
 * Python half enabled in config.yaml, the Desktop half copied in by Electron
 * and switched on by the user. Run through scripts/test-in-hermes.sh, which
 * stages the package (PROMPT_REFINEMENT_PACKAGE) and adds the fixture's
 * pre-launch hook.
 *
 * Prerequisite: `pnpm run build` (dist/). Screenshots land in the test output dir.
 */

import fs from 'node:fs'
import path from 'node:path'

import { type MockBackendFixture, setupMockBackend, waitForAppReady } from './fixtures'
import { expect, test } from './test'

const AGENT_REPLY = 'Acknowledged: working on the refined task.'

const DRAFT_AUTO = 'fix the flaky upload test in src/upload.test.ts and do not change any other files'
const REFINED_AUTO = 'Fix the flaky upload test in src/upload.test.ts.\n\nConstraint: do not change any other files.'

// Held by the mock (see beforeAll) so the progress drawer can be seen and canceled.
const DRAFT_CANCEL = 'summarize the open issues about the release checklist for this week'

const DRAFT_MANUAL = 'rename the helper in src/utils/format.ts and update its callers'
const REFINED_MANUAL = 'Rename the helper in src/utils/format.ts and update its callers to match.'

const DRAFT_BLOCKED = 'migrate the legacy settings in config/legacy.yaml to the new schema'
const REFINED_BLOCKED = 'Migrate the legacy settings to the new schema.'

// The mock answers this one with JSON it cannot finish: the refinement fails.
const DRAFT_FAIL = 'outline the rollback steps for the payments migration'

// Read-only request; the mock's rewrite adds a delete the user never asked for.
const DRAFT_INTENT = 'explain how the retry logic in the upload client works'
const REFINED_INTENT = 'Explain how the retry logic in the upload client works, then delete the unused retry helpers.'

const answer = (prompt: string, why: string) =>
  JSON.stringify({
    prompt,
    professional: why,
    raw_material: 'The current source and its callers.',
    methods: 'Repository-wide search and the existing test suite.',
    verification: 'The full test suite passes before and after.'
  })

/** The refinement call's input wraps the draft; agent turns never do. */
function refineOrReply(prompt: string): string {
  if (!prompt.includes('<draft_prompt>')) {
    return AGENT_REPLY
  }

  if (prompt.includes('rollback steps for the payments migration')) {
    return '{"prompt": '
  }

  if (prompt.includes('retry logic in the upload client')) {
    return answer(REFINED_INTENT, 'Trace one failing request end to end.')
  }

  if (prompt.includes('config/legacy.yaml')) {
    return answer(REFINED_BLOCKED, 'Migrate with a reversible plan.')
  }

  if (prompt.includes('flaky upload test')) {
    return answer(REFINED_AUTO, 'Reproduce the flake before changing anything.')
  }

  if (prompt.includes('src/utils/format.ts')) {
    return answer(REFINED_MANUAL, 'Rename through every call site, not by hand.')
  }

  return 'Summarize this week’s open issues about the release checklist.'
}

let fixture: MockBackendFixture | null = null

/** Prompts that reached a model OTHER than the refinement call (agent turns, titles). */
const agentPrompts = () => fixture!.mock.receivedPrompts.filter(prompt => !prompt.includes('<draft_prompt>'))
const refinementPrompts = () => fixture!.mock.receivedPrompts.filter(prompt => prompt.includes('<draft_prompt>'))

const composer = () => fixture!.page.locator('[data-slot="composer-root"] [contenteditable]').first()
const drawer = () => fixture!.page.getByRole('region', { name: 'Prompt refinement' })

async function startNewChat() {
  const page = fixture!.page
  await page.evaluate(() => (window.location.hash = '#/'))
  await composer().waitFor({ state: 'visible', timeout: 30_000 })
}

async function clearComposer() {
  const page = fixture!.page
  await composer().click()
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A')
  await page.keyboard.press('Backspace')
}

async function typeAndSend(text: string) {
  const page = fixture!.page
  await clearComposer()
  await composer().type(text)
  await page.keyboard.press('Enter')
}

async function setMode(label: 'Automatic' | 'Approval-First') {
  const page = fixture!.page
  await page.evaluate(() => (window.location.hash = '#/settings?tab=plugins&plugin=prompt-refinement'))
  await page.getByRole('button', { name: label, exact: true }).click()
}

test.beforeAll(async () => {
  // A cold source backend can take longer than one test's budget to boot.
  test.setTimeout(240_000)
  fixture = await setupMockBackend({
    mockServer: { replyForPrompt: refineOrReply, holdFirstCompletionContaining: 'release checklist' },
    // Enable the Python half, which registers the `prompt_refinement` slot.
    extraConfig: 'plugins:\n  enabled:\n    - prompt-refinement\n',
    // Land the package where `hermes plugins install` clones it.
    seedHome: home =>
      fs.cpSync(process.env.PROMPT_REFINEMENT_PACKAGE!, path.join(home, 'plugins', 'prompt-refinement'), {
        recursive: true
      })
  })
  await waitForAppReady(fixture!, 200_000)

  // A package's Desktop half ships opt-in: record the user's "on" (what the
  // Plugins page toggle writes) and reload so the loader activates it.
  const page = fixture!.page
  await page.evaluate(() =>
    window.localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ 'prompt-refinement': true }))
  )
  await page.reload()
  await waitForAppReady(fixture!, 200_000)
  const copied = path.join(fixture!.sandbox.hermesHome, 'desktop-plugins', 'prompt-refinement')
  await expect.poll(() => fs.existsSync(path.join(copied, 'plugin.js')), { timeout: 60_000 }).toBe(true)
})

test.afterAll(async () => {
  await fixture?.cleanup()
  fixture = null
})

test.describe.serial('prompt refinement on an older Desktop', () => {
  test('its settings page says it needs a newer Hermes Desktop', async () => {
    const page = fixture!.page
    await page.evaluate(() => (window.location.hash = '#/settings?tab=plugins&plugin=prompt-refinement'))
    await expect(page.getByText('Needs a newer Hermes Desktop')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/^Missing: .*useThisComposer/)).toBeVisible()
    await page.screenshot({ path: test.info().outputPath('older-desktop-settings.png') })
  })

  test('no Refine pill, and a send goes straight to the agent with no refinement call', async () => {
    const page = fixture!.page
    await startNewChat()
    await expect(page.getByRole('button', { name: /^Prompt refinement settings/ })).toHaveCount(0)

    await typeAndSend(DRAFT_AUTO)
    await page.getByText(AGENT_REPLY).first().waitFor({ state: 'visible', timeout: 60_000 })

    expect(refinementPrompts()).toHaveLength(0)
    expect(agentPrompts().some(prompt => prompt.includes(DRAFT_AUTO))).toBe(true)
  })
})
