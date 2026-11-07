// CI: the committed build outputs are exactly what build.mjs makes from dev/src:
// desktop/plugin.js (Desktop half), shared.json (fallback instructions and
// intent rules) and dev/test/parity/expected.json (TypeScript check verdicts).
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dev = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(dev, '..')
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'prompt-refinement-build-'))

execFileSync(process.execPath, [path.join(dev, 'build.mjs'), tmp], { stdio: 'inherit' })

const files = ['desktop/plugin.js', 'shared.json', 'dev/test/parity/expected.json']
const stale = files.filter(file => fs.readFileSync(path.join(tmp, file), 'utf8') !== fs.readFileSync(path.join(repo, file), 'utf8'))

fs.rmSync(tmp, { recursive: true, force: true })

if (stale.length) {
  console.error(`Out of date: ${stale.join(', ')}. Run \`npm run build\` in dev/ and commit the result.`)
  process.exit(1)
}

console.log(`${files.join(', ')} match dev/src`)
