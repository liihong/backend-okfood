import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

const projectRoot = resolve(fileURLToPath(new URL('.', import.meta.url)))
const staticSrc = join(projectRoot, 'static')
const babelHelpersSrc = join(projectRoot, 'node_modules/@babel/runtime/helpers')
/**
 * 上传勾选「将 JS 编译成 ES5」时，微信会对仍含 async 等的文件注入
 * require('@babel/runtime/helpers/...')，路径相对 utils/ 下的业务脚本。
 */

/**
 * uni-app 仅复制「被源码引用」的 static 资源；自定义 tabBar 在运行时拼路径，
 * order-*.png 等不会进入依赖图。构建/开发结束后整目录同步到 mp-weixin 产物。
 */
function copyProjectStaticPlugin() {
  return {
    name: 'copy-project-static',
    writeBundle(options) {
      const outDir = options.dir
      if (!outDir || !outDir.replace(/\\/g, '/').includes('mp-weixin')) return
      if (!existsSync(staticSrc)) return
      const dest = join(outDir, 'static')
      mkdirSync(dest, { recursive: true })
      cpSync(staticSrc, dest, { recursive: true })
    },
  }
}

function patchMpWeixinProjectConfigPlugin() {
  return {
    name: 'patch-mp-weixin-project-config',
    writeBundle(options) {
      const outDir = options.dir
      if (!outDir || !outDir.replace(/\\/g, '/').includes('mp-weixin')) return
      const cfgPath = join(outDir, 'project.config.json')
      if (!existsSync(cfgPath)) return
      const cfg = JSON.parse(readFileSync(cfgPath, 'utf8'))
      const isDevOut = outDir.replace(/\\/g, '/').includes('/dev/')
      cfg.setting = {
        ...cfg.setting,
        es6: !isDevOut,
        enhance: false,
        minified: isDevOut ? false : true,
      }
      writeFileSync(cfgPath, `${JSON.stringify(cfg, null, 2)}\n`, 'utf8')
    },
  }
}

function copyBabelRuntimeToMpOut(outDir) {
  if (!outDir || !outDir.replace(/\\/g, '/').includes('mp-weixin')) return
  if (!existsSync(babelHelpersSrc)) return
  const destDir = join(outDir, 'utils/@babel/runtime/helpers')
  mkdirSync(destDir, { recursive: true })
  for (const name of readdirSync(babelHelpersSrc)) {
    if (!name.endsWith('.js') || name.startsWith('esm')) continue
    cpSync(join(babelHelpersSrc, name), join(destDir, name))
  }
}

function copyBabelRuntimeForMpWeixinPlugin() {
  let lastMpOutDir = ''
  return {
    name: 'copy-babel-runtime-mp-weixin',
    writeBundle(options) {
      if (options.dir?.replace(/\\/g, '/').includes('mp-weixin')) {
        lastMpOutDir = options.dir
      }
    },
    closeBundle() {
      copyBabelRuntimeToMpOut(lastMpOutDir)
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    uni(),
    copyProjectStaticPlugin(),
    patchMpWeixinProjectConfigPlugin(),
    copyBabelRuntimeForMpWeixinPlugin(),
  ],
})
