// Build what the plugin installs from dev/ sources, into the repository root:
//   desktop/plugin.js   the Desktop half (dev/src/plugin.tsx), one ESM file
//                       Hermes Desktop loads uncompiled from disk
//   shared.json         what the /refine-prompt fallback shares with it
// and dev/test/parity/expected.json (the TypeScript checks' verdicts).
//
// Desktop lets a disk plugin import only `@hermes/plugin-sdk`, `react` and
// `react/jsx-runtime`, and its SDK shim exports only the names the running
// Desktop has. So every SDK import is routed through one generated module
// that reads the SDK as a namespace: on an older Desktop a missing name is
// `undefined` (src/sdk-support.ts then keeps the plugin inactive) instead of
// a module-link error that stops the plugin from loading at all.
//
//   node build.mjs           write into the repository
//   node build.mjs <dir>     write the same files under <dir> (the CI check)

import { build } from 'esbuild'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const dev = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(dev, '..')
const out = path.resolve(process.argv[2] ?? repo)
const outfile = path.join(out, 'desktop/plugin.js')
const SDK = '@hermes/plugin-sdk'

/** Every value name the source imports from the SDK (type-only imports are skipped). */
function sdkNames() {
  // atom and computed: scripts/nanostores-from-sdk.js re-exports them.
  const names = new Set(['atom', 'computed'])
  const src = path.join(dev, 'src')

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
  entryPoints: [path.join(dev, 'src/plugin.tsx')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  jsx: 'automatic',
  legalComments: 'none',
  external: ['react', 'react/jsx-runtime'],
  // The SDK re-exports nanostores' `atom`; a disk plugin cannot import nanostores itself.
  alias: { nanostores: path.join(dev, 'scripts/nanostores-from-sdk.js') },
  plugins: [sdkCompat],
  banner: { js: '// Prompt Refinement for Hermes Desktop. Built from dev/src/ by dev/build.mjs; do not edit.' },
  logLevel: 'warning'
})

console.log(`built ${path.relative(repo, outfile)}`)

// The stock-Hermes fallback (Python) shares the refinement instructions and the
// intent rules with the Desktop half, and must reach the same check verdicts.
const entryOut = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'prompt-refinement-shared-')), 'shared.mjs')

await build({
  entryPoints: [path.join(dev, 'scripts/shared-entry.ts')],
  outfile: entryOut,
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node20',
  logLevel: 'warning'
})

const { parity, shared } = await import(pathToFileURL(entryOut).href)
const inputs = JSON.parse(fs.readFileSync(path.join(dev, 'test/parity/inputs.json'), 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

writeJson(path.join(out, 'shared.json'), shared())
writeJson(path.join(out, 'dev/test/parity/expected.json'), parity(inputs))
fs.rmSync(path.dirname(entryOut), { recursive: true, force: true })
console.log('built shared.json, dev/test/parity/expected.json')
