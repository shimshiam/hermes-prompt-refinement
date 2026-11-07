/**
 * Feature detection for the host SDK.
 *
 * Off / Approval-First / Automatic rely on Desktop SDK additions newer than
 * the plugin API itself: the send origin and `failClosed` on composer
 * middleware, `host.composer.hold`, `useThisComposer()`,
 * `host.requestForSession()` and the `ComposerDrawer` / `Slider` exports.
 * On a Desktop without them the plugin registers no middleware at all (so it
 * can never touch a send) and shows a settings page that says what is missing.
 *
 * The send origin cannot be probed here; the middleware only ever acts on a
 * draft whose `origin.kind` is `typed`, so a host that does not stamp it gets
 * every send passed through untouched.
 */

import * as sdk from '@hermes/plugin-sdk'

type Probe = Record<string, unknown> & {
  host?: { composer?: Record<string, unknown>; requestForSession?: unknown }
}

/** Names of the host features this plugin needs that the running Desktop lacks. */
export function missingHostFeatures(api: Probe = sdk as unknown as Probe): string[] {
  const missing: string[] = []

  if (typeof api.useThisComposer !== 'function') {
    missing.push('useThisComposer')
  }

  if (api.ComposerDrawer === undefined) {
    missing.push('ComposerDrawer')
  }

  if (api.Slider === undefined) {
    missing.push('Slider')
  }

  if (typeof api.host?.composer?.hold !== 'function') {
    missing.push('host.composer.hold')
  }

  if (typeof api.host?.requestForSession !== 'function') {
    missing.push('host.requestForSession')
  }

  return missing
}
