import { describe, expect, it } from 'vitest'
import type { VersionInfo } from '@/lib/types'
import { isReadOnlyVersion, versionLabel, warningText } from './version'

const v = (extra: Partial<VersionInfo>): VersionInfo => ({
  id: 'x',
  name: '我的版本',
  kind: 'edited',
  source: 'ai',
  created: null,
  source_deleted: false,
  ...extra,
})

describe('isReadOnlyVersion', () => {
  it('AI 譜與舊 AI 譜唯讀，編輯版本可改', () => {
    const list = [v({ id: 'old1', kind: 'old_ai' }), v({ id: 'e1' })]
    expect(isReadOnlyVersion('ai', list)).toBe(true)
    expect(isReadOnlyVersion('ai', undefined)).toBe(true)
    expect(isReadOnlyVersion('old1', list)).toBe(true)
    expect(isReadOnlyVersion('e1', list)).toBe(false)
    expect(isReadOnlyVersion('e1', undefined)).toBe(false)
  })
})

describe('versionLabel', () => {
  it('標示唯讀、來源已刪除、對齊警告', () => {
    expect(versionLabel(v({ kind: 'ai', name: 'AI 譜' }))).toBe('AI 譜（唯讀）')
    expect(versionLabel(v({ kind: 'old_ai', name: '舊 AI 譜 1' }))).toBe('舊 AI 譜 1（唯讀）')
    expect(versionLabel(v({ source_deleted: true }))).toBe('我的版本（來源已刪除）')
    expect(versionLabel(v({ warning: { old_ai: 'o', bars: [0], message: 'm' } }))).toBe(
      '我的版本 ⚠'
    )
  })
})

describe('warningText', () => {
  it('小節編號改成 1 起算', () => {
    expect(warningText({ old_ai: 'o', bars: [0, 4], message: '對不齊' })).toBe(
      '對不齊（第 1、5 小節）'
    )
  })
})
