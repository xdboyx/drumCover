/** 影片標題 → 專案名稱：Windows 非法字元與控制字元換成 `_`、去頭尾空白、最多 80 字。 */
export function sanitizeProjectName(title: string): string {
  // eslint-disable-next-line no-control-regex
  return title.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim().slice(0, 80)
}
