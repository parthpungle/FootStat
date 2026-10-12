export const formatXg = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? '—' : value.toFixed(digits)

export const formatPercent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`

export const formatInt = (value: number) => value.toLocaleString()

/** "2022-11-20" -> "20 Nov" (parsed as a calendar date, no timezone shift). */
export function formatShortDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return iso
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' })
}
