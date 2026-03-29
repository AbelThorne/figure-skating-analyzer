const JUMP_PATTERN = /^([1-4]?)(A|T|S|Lo|Lz|F)\b/;
const SPIN_PATTERN = /Sp[B0-4]?$/;
const STEP_PATTERN = /^(StSq|ChSq)/;
const LEVEL_PATTERN = /(\d)$/;

export type ElementType = "jump" | "spin" | "step";

export function classifyElement(name: string): ElementType | null {
  if (JUMP_PATTERN.test(name)) return "jump";
  if (SPIN_PATTERN.test(name)) return "spin";
  if (STEP_PATTERN.test(name)) return "step";
  return null;
}

export function isJumpElement(name: string): boolean {
  return JUMP_PATTERN.test(name);
}

export function isSpinElement(name: string): boolean {
  return SPIN_PATTERN.test(name);
}

export function isStepElement(name: string): boolean {
  return STEP_PATTERN.test(name);
}

export function extractJumpType(name: string): string | null {
  const m = name.match(JUMP_PATTERN);
  if (!m) return null;
  const rotation = m[1] || "1";
  return `${rotation}${m[2]}`;
}

export function elementLevel(name: string): number {
  const m = name.match(LEVEL_PATTERN);
  if (m) return parseInt(m[1], 10);
  if (/B$/.test(name)) return 0.5;
  return 0;
}
