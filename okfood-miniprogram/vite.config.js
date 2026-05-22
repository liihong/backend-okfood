import { cpSync, existsSync, mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

const projectRoot = resolve(fileURLToPath(new URL('.', import.meta.url)))
const staticSrc = join(projectRoot, 'static')

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

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [uni(), copyProjectStaticPlugin()],
})
