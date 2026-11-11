import { create } from 'zustand'

/**
 * 首頁已經「看過、收起來」的工作結果（完成或失敗）。
 * 工作狀態是全站共用、伺服器端保留到下一個工作開始，所以首頁需要記住使用者已經處理掉哪一個。
 * 只存在記憶體；重新整理後會再顯示一次（失敗的重試入口不能憑空消失）。
 */
interface ImportUiState {
  dismissed: string | null
  dismiss: (key: string) => void
  reset: () => void
}

export const useImportUi = create<ImportUiState>((set) => ({
  dismissed: null,
  dismiss: (key) => set({ dismissed: key }),
  reset: () => set({ dismissed: null }),
}))

export const resultKey = (project: string | undefined, state: string) => `${project ?? ''}:${state}`
