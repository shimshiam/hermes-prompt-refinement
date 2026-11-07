import { defineConfig } from 'vitest/config'

// Standalone tests: the plugin's pure logic plus the SDK guard. The UI and
// real-composer tests need a Hermes checkout: scripts/test-in-hermes.sh.
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@hermes/plugin-sdk': new URL('./test/sdk-stub.ts', import.meta.url).pathname } },
  test: {
    include: [
      'src/cache.test.ts',
      'src/chat-context.test.ts',
      'src/engine.test.ts',
      'src/intent.test.ts',
      'src/preservation.test.ts',
      'src/review-store.test.ts',
      'src/settings.test.ts',
      'test/*.test.ts'
    ]
  }
})
