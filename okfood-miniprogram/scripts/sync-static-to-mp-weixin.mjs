/**
 * 将项目根 static/ 同步到微信小程序产物（dev / build）。
 * 用法：node scripts/sync-static-to-mp-weixin.mjs [dev|build|all]
 */
import { cpSync, existsSync, mkdirSync, readdirSync } from 'node:fs'
import { join, resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const staticSrc = join(root, 'static')
const babelHelpersSrc = join(root, 'node_modules/@babel/runtime/helpers')
const mode = (process.argv[2] || 'all').toLowerCase()

function copyBabelRuntime(outRoot) {
  if (!existsSync(babelHelpersSrc)) return
  const destDir = join(outRoot, 'utils/@babel/runtime/helpers')
  mkdirSync(destDir, { recursive: true })
  for (const name of readdirSync(babelHelpersSrc)) {
    if (!name.endsWith('.js')) continue
    cpSync(join(babelHelpersSrc, name), join(destDir, name))
  }
  console.log('[sync-static] babel helpers ->', destDir)
}

const targets =
  mode === 'dev'
    ? ['dev']
    : mode === 'build'
      ? ['build']
      : ['dev', 'build']

if (!existsSync(staticSrc)) {
  console.error('[sync-static] missing', staticSrc)
  process.exit(1)
}

for (const sub of targets) {
  const dest = join(root, 'dist', sub, 'mp-weixin', 'static')
  const outRoot = join(root, 'dist', sub, 'mp-weixin')
  if (!existsSync(outRoot)) {
    console.warn('[sync-static] skip (not built yet):', outRoot)
    continue
  }
  mkdirSync(dest, { recursive: true })
  cpSync(staticSrc, dest, { recursive: true })
  console.log('[sync-static] copied ->', dest)
  copyBabelRuntime(outRoot)
}
