// Build the Desktop half: src/plugin.tsx -> desktop/plugin.js, one ESM file
// that Hermes Desktop loads uncompiled from disk.
//
// Desktop lets a disk plugin import only `@hermes/plugin-sdk`, `react` and
// `react/jsx-runtime`, and its SDK shim exports only the names the running
// Desktop has. So every SDK import is routed through one generated module
// that reads the SDK as a namespace: on an older Desktop a missing name is
// `undefined` (src/sdk-support.ts then keeps the plugin inactive) instead of
// a module-link error that stops the plugin from loading at all.
//
//   node build.mjs                 write desktop/plugin.js
//   node build.mjs <outfile>       write elsewhere (used by the CI check)

import { build } from 'esbuild'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))
const outfile = path.resolve(process.argv[2] ?? path.join(root, 'desktop/plugin.js'))
const SDK = '@hermes/plugin-sdk'

/** Every value name the source imports from the SDK (type-only imports are skipped). */
function sdkNames() {
  // atom and computed: scripts/nanostores-from-sdk.js re-exports them.
  const names = new Set(['atom', 'computed'])
  const src = path.join(root, 'src')

  for (const file of fs.readdirSync(src)) {
    if (!/\.tsx?$/.test(file) || /\.test\.tsx?$/.test(file)) {
      continue
    }

    const text = fs.readFileSync(path.join(src, file), 'utf8')

    for (const match of text.matchAll(/import\s+(type\s+)?\{([^}]*)\}\s+from\s+'@hermes\/plugin-sdk'/g)) {
      if (match[1]) {
        continue
      }

      for (const part of match[2].split(',')) {
        const name = part.trim()

        if (name && !name.startsWith('type ')) {
          names.add(name.split(/\s+as\s+/)[0].trim())
        }
      }
    }
  }

  return [...names].sort()
}

const sdkCompat = {
  name: 'sdk-compat',
  setup(b) {
    b.onResolve({ filter: /^@hermes\/plugin-sdk$/ }, args =>
      args.namespace === 'sdk-compat' ? { path: SDK, external: true } : { path: 'sdk', namespace: 'sdk-compat' }
    )
    b.onLoad({ filter: /.*/, namespace: 'sdk-compat' }, () => ({
      contents: [
        `import * as sdk from '${SDK}'`,
        'export default sdk.default',
        ...sdkNames().map(name => `export const ${name} = sdk.${name}`)
      ].join('\n'),
      loader: 'js'
    }))
  }
}

await build({
  entryPoints: [path.join(root, 'src/plugin.tsx')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  jsx: 'automatic',
  legalComments: 'none',
  external: ['react', 'react/jsx-runtime'],
  // The SDK re-exports nanostores' `atom`; a disk plugin cannot import nanostores itself.
  alias: { nanostores: path.join(root, 'scripts/nanostores-from-sdk.js') },
  plugins: [sdkCompat],
  banner: { js: '// Prompt Refinement for Hermes Desktop. Built from src/ by build.mjs; do not edit.' },
  logLevel: 'warning'
})

console.log(`built ${path.relative(root, outfile)}`)
