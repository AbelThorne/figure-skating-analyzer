/**
 * Figure skating season utilities.
 * A season "2025-2026" runs from 2025-08-01 to 2026-07-31.
 */

/** Returns { from, to } ISO date strings for a season like "2025-2026". */
export function seasonDateRange(season: string): { from: string; to: string } {
  const [startYear] = season.split("-").map(Number);
  return {
    from: `${startYear}-08-01`,
    to: `${startYear + 1}-07-31`,
  };
}

/** Returns the current season string, e.g. "2025-2026". */
export function currentSeason(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1; // 1-indexed
  // August onwards = new season
  const startYear = month >= 8 ? year : year - 1;
  return `${startYear}-${startYear + 1}`;
}
