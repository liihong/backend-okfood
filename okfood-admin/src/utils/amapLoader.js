/**
 * 加载高德 JS API（单例）；与配送区域页共用安全码配置。
 * @param {string} key
 * @param {string} securityCode
 * @param {string[]} [plugins]
 */
export function loadAmapOnce(key, securityCode, plugins = []) {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error('无浏览器环境'))
      return
    }
    if (window.AMap) {
      resolve(window.AMap)
      return
    }
    const sec = String(securityCode || '').trim()
    if (sec) {
      window._AMapSecurityConfig = { securityJsCode: sec }
    } else {
      delete window._AMapSecurityConfig
    }

    const runLoader = () => {
      window.AMapLoader.load({
        key: String(key || '').trim(),
        version: '2.0',
        plugins,
      })
        .then((AMap) => {
          window.AMap = AMap
          resolve(AMap)
        })
        .catch((e) => reject(e instanceof Error ? e : new Error(String(e))))
    }

    if (window.AMapLoader) {
      runLoader()
      return
    }
    const s = document.createElement('script')
    s.src = 'https://webapi.amap.com/loader.js'
    s.onload = () => runLoader()
    s.onerror = () => reject(new Error('高德地图 Loader 加载失败'))
    document.head.appendChild(s)
  })
}
