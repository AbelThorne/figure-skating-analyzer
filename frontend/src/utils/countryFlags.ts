// Alpha-3 → Alpha-2 mapping for countries appearing in figure skating
const ALPHA3_TO_ALPHA2: Record<string, string> = {
  AUS: "AU", AUT: "AT", AZE: "AZ", BEL: "BE", BLR: "BY",
  BRA: "BR", CAN: "CA", CHN: "CN", CRO: "HR", CZE: "CZ",
  DEN: "DK", ESP: "ES", EST: "EE", FIN: "FI", FRA: "FR",
  GBR: "GB", GEO: "GE", GER: "DE", GRE: "GR", HUN: "HU",
  IND: "IN", ISR: "IL", ITA: "IT", JPN: "JP", KAZ: "KZ",
  KOR: "KR", LAT: "LV", LTU: "LT", MEX: "MX", NED: "NL",
  NOR: "NO", PHI: "PH", POL: "PL", POR: "PT", ROU: "RO",
  RSA: "ZA", RUS: "RU", SLO: "SI", SUI: "CH", SVK: "SK",
  SWE: "SE", THA: "TH", TPE: "TW", TUR: "TR", UKR: "UA",
  USA: "US", UZB: "UZ",
};

/**
 * Convert an alpha-3 country code to a flag emoji.
 * Returns the flag emoji or null if the code is unknown.
 */
export function countryFlag(alpha3: string | null | undefined): string | null {
  if (!alpha3) return null;
  const alpha2 = ALPHA3_TO_ALPHA2[alpha3.toUpperCase()];
  if (!alpha2) return null;
  return String.fromCodePoint(
    0x1f1e6 + alpha2.charCodeAt(0) - 0x41,
    0x1f1e6 + alpha2.charCodeAt(1) - 0x41,
  );
}
