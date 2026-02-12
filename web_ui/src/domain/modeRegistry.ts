export type ModeToken = "CV" | "DC" | "AC" | "CDL" | "EIS" | "CA" | "LSV";

export interface ModeDefinition {
  token: ModeToken;
  label: string;
}

const MODE_DEFINITIONS: ReadonlyArray<ModeDefinition> = [
  { token: "CV", label: "Cyclic Voltammetry" },
  { token: "DC", label: "Electrolysis DC" },
  { token: "AC", label: "Electrolysis AC" },
  { token: "CDL", label: "Capacitance (CDL)" },
  { token: "EIS", label: "Impedance (EIS)" },
  { token: "CA", label: "Chronoamperometry (CA)" },
  { token: "LSV", label: "Linear Sweep Voltammetry (LSV)" }
];

const MODE_TOKEN_SET = new Set(MODE_DEFINITIONS.map((item) => item.token));

export function listModeDefinitions(): ReadonlyArray<ModeDefinition> {
  return MODE_DEFINITIONS;
}

export function normalizeModeToken(raw: string): ModeToken {
  const candidate = (raw || "").trim().toUpperCase();
  if (!MODE_TOKEN_SET.has(candidate as ModeToken)) {
    throw new Error(`mode.unsupported: ${raw}`);
  }
  return candidate as ModeToken;
}

export function modeLabel(token: ModeToken): string {
  return MODE_DEFINITIONS.find((item) => item.token === token)?.label || token;
}
