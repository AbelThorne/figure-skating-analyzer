import type { ProgramRulesData } from "../api/client";
import type { ProgramElement, ValidationResult } from "./program-validator";
import { validateProgram, countViolations } from "./program-validator";

export interface CategoryMatch {
  categoryName: string;
  categoryLabel: string;
  segmentKey: string;
  segmentLabel: string;
  violations: number;
  results: ValidationResult[];
}

/**
 * Match a program against all categories and segments, returning them sorted
 * by number of violations (ascending). Categories with 0 violations are "compatible".
 */
export function matchCategories(
  elements: ProgramElement[],
  rulesData: ProgramRulesData,
): CategoryMatch[] {
  const matches: CategoryMatch[] = [];

  for (const [catName, cat] of Object.entries(rulesData.categories)) {
    for (const [segKey, seg] of Object.entries(cat.segments)) {
      const results = validateProgram(elements, seg);
      matches.push({
        categoryName: catName,
        categoryLabel: cat.label,
        segmentKey: segKey,
        segmentLabel: seg.label ?? segKey,
        violations: countViolations(results),
        results,
      });
    }
  }

  // Sort: compatible first (0 violations), then by violations ascending
  // Among compatible categories, sort by restrictiveness (more rules = more restrictive)
  matches.sort((a, b) => {
    if (a.violations !== b.violations) return a.violations - b.violations;
    // More validation results = more restrictive = show first
    return b.results.length - a.results.length;
  });

  return matches;
}

/**
 * Get the best matching category (fewest violations, most restrictive among ties).
 */
export function getBestMatch(matches: CategoryMatch[]): CategoryMatch | null {
  return matches.length > 0 ? matches[0] : null;
}

/**
 * Get all compatible categories (0 violations).
 */
export function getCompatibleCategories(matches: CategoryMatch[]): CategoryMatch[] {
  return matches.filter(m => m.violations === 0);
}
