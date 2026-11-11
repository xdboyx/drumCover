import { describe, expect, it } from 'vitest'
import { sanitizeProjectName } from './sanitize-name'

describe('sanitizeProjectName', () => {
  it('把 Windows 非法字元換成底線', () => {
    expect(sanitizeProjectName('a<b>c:d"e/f\\g|h?i*j')).toBe('a_b_c_d_e_f_g_h_i_j')
  })
  it('控制字元換成底線、去頭尾空白', () => {
    expect(sanitizeProjectName('  x\ty\n ')).toBe('x_y_')
  })
  it('最多 80 字', () => {
    expect(sanitizeProjectName('字'.repeat(100))).toHaveLength(80)
  })
  it('中文與空白保留', () => {
    expect(sanitizeProjectName('夜に駆ける - YOASOBI')).toBe('夜に駆ける - YOASOBI')
  })
})
