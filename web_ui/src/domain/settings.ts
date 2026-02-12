import { SevaUiError } from "./errors";

export const SETTINGS_STORAGE_KEY = "seva.web.settings.v1";
export const SETTINGS_SCHEMA_VERSION = 1;

export interface BoxConnectionDto {
  boxId: string;
  baseUrl: string;
  apiKey: string;
}

export interface WebSettingsDto {
  version: number;
  boxes: BoxConnectionDto[];
  requestTimeoutS: number;
  downloadTimeoutS: number;
  pollIntervalMs: number;
  pollBackoffMaxMs: number;
  resultsDir: string;
  experimentName: string;
  subdir: string;
  autoDownloadOnComplete: boolean;
  useStreaming: boolean;
  debugLogging: boolean;
  relayIp: string;
  relayPort: number;
  firmwarePathHint: string;
}

export function defaultSettings(): WebSettingsDto {
  return {
    version: SETTINGS_SCHEMA_VERSION,
    boxes: [
      { boxId: "A", baseUrl: "", apiKey: "" },
      { boxId: "B", baseUrl: "", apiKey: "" },
      { boxId: "C", baseUrl: "", apiKey: "" },
      { boxId: "D", baseUrl: "", apiKey: "" }
    ],
    requestTimeoutS: 10,
    downloadTimeoutS: 60,
    pollIntervalMs: 750,
    pollBackoffMaxMs: 5000,
    resultsDir: ".",
    experimentName: "",
    subdir: "",
    autoDownloadOnComplete: true,
    useStreaming: false,
    debugLogging: false,
    relayIp: "",
    relayPort: 0,
    firmwarePathHint: ""
  };
}

function assertFiniteNumber(value: unknown, field: string, min: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min) {
    throw new SevaUiError({
      code: "settings.invalid_number",
      message: `${field} must be a number >= ${min}.`
    });
  }
  return parsed;
}

function normalizeBox(input: unknown): BoxConnectionDto {
  const candidate = input as Partial<BoxConnectionDto>;
  const boxId = String(candidate.boxId || "").trim();
  if (!boxId) {
    throw new SevaUiError({
      code: "settings.invalid_box_id",
      message: "Each box requires a non-empty boxId."
    });
  }
  return {
    boxId,
    baseUrl: String(candidate.baseUrl || "").trim(),
    apiKey: String(candidate.apiKey || "")
  };
}

export function normalizeSettings(input: unknown): WebSettingsDto {
  const defaults = defaultSettings();
  const candidate = (input || {}) as Partial<WebSettingsDto>;
  const boxesRaw = Array.isArray(candidate.boxes) ? candidate.boxes : defaults.boxes;
  const boxes = boxesRaw.map((item) => normalizeBox(item));
  const distinct = new Set(boxes.map((item) => item.boxId.toUpperCase()));
  if (distinct.size !== boxes.length) {
    throw new SevaUiError({
      code: "settings.duplicate_box_id",
      message: "boxId values must be unique."
    });
  }

  const version = Number(candidate.version ?? defaults.version);
  if (version !== SETTINGS_SCHEMA_VERSION) {
    throw new SevaUiError({
      code: "settings.unsupported_version",
      message: `Unsupported settings version ${version}.`
    });
  }

  return {
    version,
    boxes,
    requestTimeoutS: assertFiniteNumber(candidate.requestTimeoutS ?? defaults.requestTimeoutS, "requestTimeoutS", 1),
    downloadTimeoutS: assertFiniteNumber(
      candidate.downloadTimeoutS ?? defaults.downloadTimeoutS,
      "downloadTimeoutS",
      1
    ),
    pollIntervalMs: assertFiniteNumber(candidate.pollIntervalMs ?? defaults.pollIntervalMs, "pollIntervalMs", 100),
    pollBackoffMaxMs: assertFiniteNumber(
      candidate.pollBackoffMaxMs ?? defaults.pollBackoffMaxMs,
      "pollBackoffMaxMs",
      100
    ),
    resultsDir: String(candidate.resultsDir ?? defaults.resultsDir),
    experimentName: String(candidate.experimentName ?? defaults.experimentName),
    subdir: String(candidate.subdir ?? defaults.subdir),
    autoDownloadOnComplete: Boolean(candidate.autoDownloadOnComplete ?? defaults.autoDownloadOnComplete),
    useStreaming: Boolean(candidate.useStreaming ?? defaults.useStreaming),
    debugLogging: Boolean(candidate.debugLogging ?? defaults.debugLogging),
    relayIp: String(candidate.relayIp ?? defaults.relayIp),
    relayPort: assertFiniteNumber(candidate.relayPort ?? defaults.relayPort, "relayPort", 0),
    firmwarePathHint: String(candidate.firmwarePathHint ?? defaults.firmwarePathHint)
  };
}

export function configuredBoxes(settings: WebSettingsDto): BoxConnectionDto[] {
  return settings.boxes.filter((box) => box.baseUrl.trim().length > 0);
}
