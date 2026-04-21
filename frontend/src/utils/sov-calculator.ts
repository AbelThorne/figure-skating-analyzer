import type { SovData, SovElement } from "../api/client";

/** Jump rotation number extracted from code (e.g., "3" from "3Lz"). */
function getJumpRotation(code: string): number | null {
  const m = code.match(/^(\d)/);
  return m ? parseInt(m[1], 10) : null;
}

/** Downgrade a jump code by reducing rotation by 1 (e.g., "3Lz" → "2Lz", "2A" → "1A"). */
function downgradeCode(code: string): string | null {
  const rotation = getJumpRotation(code);
  if (rotation == null || rotation <= 1) return null;
  return code.replace(/^\d/, String(rotation - 1));
}

/**
 * Compose the SOV lookup code from a base element code and its active markers.
 *
 * - Markers `e` and `<` add suffixes to the code (order: `e` then `<`).
 * - Marker `<<` transforms the code to rotation-1 (then any `e` suffix is applied).
 * - Marker `V` adds `V` suffix (spins only — e.g., CCoSp3 → CCoSp3V).
 * - Markers `q`, `!`, `*`, `x`, `+REP` do NOT affect the SOV lookup code.
 *
 * Returns null if the composed code doesn't exist in the SOV (e.g., downgrading a 1T).
 */
export function composeSovCode(baseCode: string, markers: string[]): string | null {
  const hasDowngrade = markers.includes("<<");
  const hasEdge = markers.includes("e");
  const hasUnderRotation = markers.includes("<");
  const hasV = markers.includes("V");

  let code = baseCode;

  if (hasDowngrade) {
    const downgraded = downgradeCode(code);
    if (!downgraded) return null;
    code = downgraded;
  }

  // Build suffix: V for spins, edge then under-rotation for jumps
  if (hasV) code += "V";
  if (hasEdge) code += "e";
  if (hasUnderRotation && !hasDowngrade) code += "<";

  return code;
}

/**
 * Look up a SOV element by its composed code.
 */
export function lookupSov(sov: SovData, code: string): SovElement | null {
  return sov.elements[code] ?? null;
}

/**
 * Calculate the effective base value for a single element (not a combo).
 */
export function calculateElementBV(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number {
  if (markers.includes("*")) return 0;

  const sovCode = composeSovCode(baseCode, markers);
  if (!sovCode) return 0;

  const element = lookupSov(sov, sovCode);
  if (!element) return 0;

  let bv = element.base_value;

  if (markers.includes("x")) bv *= 1.10;
  if (markers.includes("+REP")) bv *= 0.70;

  return Math.round(bv * 100) / 100;
}

/**
 * Get the GOE array for an element after marker application.
 */
export function getElementGoe(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number[] | null {
  if (markers.includes("*")) return null;

  const sovCode = composeSovCode(baseCode, markers);
  if (!sovCode) return null;

  const element = lookupSov(sov, sovCode);
  return element?.goe ?? null;
}

/**
 * A single jump within a combo/sequence, with its own code and markers.
 */
export interface ComboJump {
  code: string;
  markers: string[];
}

/**
 * Calculate base value for a combo/sequence.
 * Sum of individual jump BVs (after per-jump markers), then apply combo-level multiplicators.
 */
export function calculateComboBV(
  sov: SovData,
  jumps: ComboJump[],
  comboMarkers: string[],
): number {
  if (comboMarkers.includes("*")) return 0;

  let totalBV = 0;
  for (const jump of jumps) {
    const jumpMarkersForBV = jump.markers.filter(m => !["x", "+REP"].includes(m));
    const bv = calculateElementBV(sov, jump.code, jumpMarkersForBV);
    totalBV += bv;
  }

  if (comboMarkers.includes("x")) totalBV *= 1.10;
  if (comboMarkers.includes("+REP")) totalBV *= 0.70;

  return Math.round(totalBV * 100) / 100;
}

/**
 * Calculate min score (BV + GOE at -5) for a single element.
 */
export function calculateElementMin(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number {
  const bv = calculateElementBV(sov, baseCode, markers);
  const goe = getElementGoe(sov, baseCode, markers);
  if (!goe) return bv;
  return Math.round((bv + goe[0]) * 100) / 100;
}

/**
 * Calculate max score (BV + GOE at +5) for a single element.
 */
export function calculateElementMax(
  sov: SovData,
  baseCode: string,
  markers: string[],
): number {
  const bv = calculateElementBV(sov, baseCode, markers);
  const goe = getElementGoe(sov, baseCode, markers);
  if (!goe) return bv;
  return Math.round((bv + goe[9]) * 100) / 100;
}

/**
 * Get full GOE breakdown for hover tooltips.
 */
export function getGoeBreakdown(
  sov: SovData,
  baseCode: string,
  markers: string[],
  side: "negative" | "positive",
): { level: number; value: number }[] | null {
  const goe = getElementGoe(sov, baseCode, markers);
  if (!goe) return null;

  const bv = calculateElementBV(sov, baseCode, markers);

  if (side === "negative") {
    return [
      { level: -5, value: Math.round((bv + goe[0]) * 100) / 100 },
      { level: -4, value: Math.round((bv + goe[1]) * 100) / 100 },
      { level: -3, value: Math.round((bv + goe[2]) * 100) / 100 },
      { level: -2, value: Math.round((bv + goe[3]) * 100) / 100 },
      { level: -1, value: Math.round((bv + goe[4]) * 100) / 100 },
    ];
  }

  return [
    { level: +1, value: Math.round((bv + goe[5]) * 100) / 100 },
    { level: +2, value: Math.round((bv + goe[6]) * 100) / 100 },
    { level: +3, value: Math.round((bv + goe[7]) * 100) / 100 },
    { level: +4, value: Math.round((bv + goe[8]) * 100) / 100 },
    { level: +5, value: Math.round((bv + goe[9]) * 100) / 100 },
  ];
}

/**
 * Check if an element code is a Flip or Lutz (for edge marker compatibility).
 */
export function isFlipOrLutz(code: string): boolean {
  return /\d[FL](?:lz|$)/i.test(code) || code.endsWith("F") || code.endsWith("Lz");
}

/**
 * Check if an element code is an Axel type.
 */
export function isAxel(code: string): boolean {
  return /\dA$/.test(code) || code === "1Eu";
}

/**
 * Check if an element code represents a jump (for combo/modifier logic).
 */
export function isJump(sov: SovData, code: string): boolean {
  const el = sov.elements[code];
  return el?.type === "jump";
}

/**
 * Get the available base element codes (without marker variants) from SOV,
 * optionally filtered by category.
 */
export function getBaseElements(
  sov: SovData,
  includePairs: boolean,
): Record<string, string[]> {
  const groups: Record<string, string[]> = {};

  for (const [code, el] of Object.entries(sov.elements)) {
    // Skip marker variants (codes containing <, e suffix, V suffix for spins)
    if (code.includes("<") || /e$/.test(code) || /V$/.test(code)) continue;
    // Skip pair elements if not included
    if (!includePairs && el.category === "pair") continue;

    const type = el.type;
    if (!groups[type]) groups[type] = [];
    groups[type].push(code);
  }

  // Sort each group
  for (const codes of Object.values(groups)) {
    codes.sort((a, b) => {
      const aRot = parseInt(a) || 0;
      const bRot = parseInt(b) || 0;
      if (aRot !== bRot) return aRot - bRot;
      return a.localeCompare(b);
    });
  }

  return groups;
}
