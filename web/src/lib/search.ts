/** Case-insensitive multi-term search over a row's text fields.
 *
 * Every whitespace-separated term must appear somewhere in the joined haystack,
 * so "kpmg audit" narrows rather than widens.
 */
export function matches(haystack: (string | null | undefined)[], query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const hay = haystack.filter(Boolean).join(' ').toLowerCase()
  return q.split(/\s+/).every((term) => hay.includes(term))
}
