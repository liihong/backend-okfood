/** 打印机品牌 */
export const PRINT_BRANDS = [
  { value: 'local_label', label: '本地标签机', cloud: false, needsKey: false },
  { value: 'xprinter_cloud_label', label: '芯烨云标签', cloud: true, needsKey: false },
  { value: 'feie_label', label: '飞鹅标签 FP-N20W', cloud: true, needsKey: true },
  { value: 'yilian_k4', label: '易联云 K4', cloud: true, needsKey: true },
]

export function brandMeta(brand) {
  return PRINT_BRANDS.find((b) => b.value === brand) || PRINT_BRANDS[0]
}
