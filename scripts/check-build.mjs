// CI: desktop/plugin.js must be exactly what build.mjs makes from src/.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'prompt-refinement-build-'))
const fresh = path.join(dir, 'plugin.js')

execFileSync(process.execPath, ['build.mjs', fresh], { stdio: 'inherit' })

if (fs.readFileSync(fresh, 'utf8') !== fs.readFileSync('desktop/plugin.js', 'utf8')) {
  console.error('desktop/plugin.js is out of date: run `npm run build` and commit it.')
  process.exit(1)
}

console.log('desktop/plugin.js matches src/')
