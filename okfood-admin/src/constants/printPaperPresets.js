/** 标签纸预设（宽×高 mm） */
export const PAPER_PRESETS = [
  { value: '76x130', label: '76×130mm（顺丰面单）', width: 76, height: 130 },
  { value: '60x90', label: '60×90mm（袋贴）', width: 60, height: 90 },
  { value: '40x30', label: '40×30mm', width: 40, height: 30 },
  { value: '80x50', label: '80×50mm', width: 80, height: 50 },
  { value: '80x60', label: '80×60mm', width: 80, height: 60 },
  { value: '100x80', label: '100×80mm', width: 100, height: 80 },
  { value: '100x150', label: '100×150mm', width: 100, height: 150 },
  { value: '100x180', label: '100×180mm', width: 100, height: 180 },
  { value: 'custom', label: '自定义', width: null, height: null },
]

export function presetSize(value) {
  return PAPER_PRESETS.find((p) => p.value === value)
}
