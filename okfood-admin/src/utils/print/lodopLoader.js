/** C-Lodop 动态加载与检测（双端口 + 就绪轮询） */

const CLODOP_SOURCES = [
  'http://localhost:8000/CLodopfuncs.js?priority=1',
  'http://localhost:18000/CLodopfuncs.js?priority=0',
  'http://127.0.0.1:8000/CLodopfuncs.js?priority=1',
  'http://127.0.0.1:18000/CLodopfuncs.js?priority=0',
  'https://localhost.lodop.net:8443/CLodopfuncs.js?priority=1',
]

let loadPromise = null

function tryGetLodop() {
  try {
    if (typeof window.getCLodop === 'function') {
      const lodop = window.getCLodop()
      if (lodop) return lodop
    }
    if (window.LODOP) return window.LODOP
  } catch {
    /* C-Lodop 尚未就绪 */
  }
  return null
}

function appendScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-clodop-src="${src}"]`)
    if (existing) {
      resolve()
      return
    }
    const s = document.createElement('script')
    s.src = src
    s.async = true
    s.dataset.clodopSrc = src
    s.onload = () => resolve()
    s.onerror = () => reject(new Error(`无法加载 ${src}`))
    document.head.appendChild(s)
  })
}

function waitForLodopReady(timeoutMs = 12000) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = () => {
      const lodop = tryGetLodop()
      if (lodop) {
        resolve(lodop)
        return
      }
      if (Date.now() - start >= timeoutMs) {
        reject(new Error('C-Lodop 未就绪，请确认服务已启动（托盘图标为运行状态）'))
        return
      }
      window.setTimeout(tick, 150)
    }
    tick()
  })
}

export function loadLodop() {
  if (typeof window === 'undefined') return Promise.reject(new Error('非浏览器环境'))

  const ready = tryGetLodop()
  if (ready) return Promise.resolve(ready)

  if (!loadPromise) {
    loadPromise = (async () => {
      let loaded = false
      for (const src of CLODOP_SOURCES) {
        try {
          await appendScript(src)
          loaded = true
        } catch {
          /* 尝试下一个端口 */
        }
      }
      if (!loaded) {
        throw new Error('无法连接 C-Lodop，请安装并启动打印服务（默认端口 8000/18000）')
      }
      return waitForLodopReady()
    })().catch((err) => {
      loadPromise = null
      throw err
    })
  }
  return loadPromise
}

export function mmToLodopUnit(mm) {
  return Math.round(Number(mm) * 10)
}

/** 列出本机打印机名称，便于排查 SET_PRINTER_INDEX 失败 */
export async function listLocalPrinters() {
  const lodop = await loadLodop()
  const count = Number(lodop.GET_PRINTER_COUNT?.()) || 0
  const names = []
  for (let i = 0; i < count; i += 1) {
    names.push(String(lodop.GET_PRINTER_NAME(i) || ''))
  }
  return names
}
