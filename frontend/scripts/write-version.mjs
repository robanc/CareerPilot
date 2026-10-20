// Writes dist/version.json with the commit being built, for the release
// smoke test (ops/smoke-test-render.sh). Run after `npm run build`.
// Render sets RENDER_GIT_COMMIT at build time; anything other than a full
// 40-character SHA is written as null, so the smoke test fails closed.
import { writeFileSync } from 'node:fs'

const raw = (process.env.RENDER_GIT_COMMIT ?? '').trim()
const commit = /^[0-9a-f]{40}$/.test(raw) ? raw : null

writeFileSync(
  new URL('../dist/version.json', import.meta.url),
  `${JSON.stringify({ commit })}\n`
)
console.log(`version.json: commit ${commit ?? 'unknown (null)'}`)
