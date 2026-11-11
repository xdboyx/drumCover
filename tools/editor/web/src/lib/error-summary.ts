/** 長錯誤訊息（例如 Python traceback）→ 一行摘要。取最後一行（通常是真正的原因），過長就截斷。 */
export function summarizeError(message: string, max = 140): { summary: string; hasMore: boolean } {
  const lines = message
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
  const last = lines.at(-1) ?? ''
  const tooLong = last.length > max
  return {
    summary: tooLong ? `${last.slice(0, max - 1)}…` : last,
    hasMore: lines.length > 1 || tooLong,
  }
}
