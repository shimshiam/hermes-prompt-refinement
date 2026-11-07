import { describe, expect, it, vi } from 'vitest'

import { missingHostFeatures } from '../src/sdk-support'

const fn = () => undefined

const current = {
  useThisComposer: fn,
  ComposerDrawer: fn,
  Slider: fn,
  host: { composer: { hold: fn }, requestForSession: fn }
}

describe('missingHostFeatures', () => {
  it('is empty on a Desktop with the composer review SDK', () => {
    expect(missingHostFeatures(current)).toEqual([])
  })

  it('names every missing piece on an older Desktop', () => {
    const older = { host: { composer: { getDraft: fn, setDraft: fn } } }

    expect(missingHostFeatures(older)).toEqual([
      'useThisComposer',
      'ComposerDrawer',
      'Slider',
      'host.composer.hold',
      'host.requestForSession'
    ])
  })
})

describe('on an older Desktop the plugin stays inactive', () => {
  it('registers no send middleware or composer UI, only a settings page saying why', async () => {
    vi.resetModules()
    // An older Desktop: every long-standing SDK name exists, the review
    // additions read as undefined (as Desktop's SDK shim makes them).
    const added = new Set(['useThisComposer', 'ComposerDrawer', 'Slider', 'composerSurfaceGlass'])

    vi.doMock('@hermes/plugin-sdk', async () => {
      const older: Record<string | symbol, unknown> = {
        ...(await vi.importActual<object>('./sdk-stub')),
        host: { composer: { getDraft: fn, setDraft: fn } }
      }

      return new Proxy(older, {
        has: () => true,
        get: (target, key) =>
          key in target ? target[key] : typeof key === 'symbol' || key === 'then' || added.has(key) ? undefined : fn
      })
    })

    const { default: plugin } = await import('../src/plugin')

    const ctx = {
      i18n: { register: vi.fn(), t: (key: string) => key },
      registerSettingsPage: vi.fn(),
      registerMany: vi.fn(),
      register: vi.fn(),
      addEventListener: vi.fn(),
      onDispose: vi.fn(),
      storage: { get: vi.fn(), set: vi.fn() }
    }

    plugin.register(ctx as never)

    expect(ctx.registerMany).not.toHaveBeenCalled()
    expect(ctx.register).not.toHaveBeenCalled()
    expect(ctx.registerSettingsPage).toHaveBeenCalledTimes(1)
    expect(ctx.registerSettingsPage.mock.calls[0][0]).toMatchObject({ id: 'settings' })
  })
})
