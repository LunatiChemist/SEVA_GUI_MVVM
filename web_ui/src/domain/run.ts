import { ModeToken, normalizeModeToken } from "./modeRegistry";
import { SevaUiError } from "./errors";

export interface RunEntryDto {
  wellId: string;
  boxId: string;
  slot: string;
  modes: ModeToken[];
  paramsByMode: Record<ModeToken, Record<string, unknown>>;
}

export interface StartGroupCommand {
  groupId: string;
  clientDateTime: string;
  experimentName: string;
  subdir?: string;
  entries: RunEntryDto[];
}

export interface RunRefDto {
  groupId: string;
  boxId: string;
  runId: string;
  wellId: string;
  slot: string;
}

export interface RunStatusDto {
  runId: string;
  boxId: string;
  wellId?: string;
  slot?: string;
  status: string;
  startedAt?: string;
  endedAt?: string;
  progressPct: number;
  remainingS?: number;
  currentMode?: string;
  remainingModes: string[];
  errorMessage?: string;
}

export interface RunGroupSnapshot {
  groupId: string;
  statuses: RunStatusDto[];
  allDone: boolean;
  polledAt: string;
}

export interface JobStatusApi {
  run_id: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  progress_pct?: number;
  remaining_s?: number;
  current_mode?: string;
  remaining_modes?: string[];
  mode?: string;
  slots?: Array<{
    slot: string;
    status: string;
    message?: string;
  }>;
}

export interface StartJobApiResponse extends JobStatusApi {}

export interface EntryDraftState {
  wellId: string;
  boxId: string;
  slot: string;
  modes: ModeToken[];
  modeParamsJson: Partial<Record<ModeToken, string>>;
}

export function createEmptyEntry(boxId = "A"): EntryDraftState {
  return {
    wellId: "",
    boxId,
    slot: "slot01",
    modes: [],
    modeParamsJson: {}
  };
}

export function normalizeEntryDraft(draft: EntryDraftState): RunEntryDto {
  const wellId = draft.wellId.trim();
  if (!wellId) {
    throw new SevaUiError({
      code: "run.missing_well_id",
      message: "wellId is required."
    });
  }
  const boxId = draft.boxId.trim();
  if (!boxId) {
    throw new SevaUiError({
      code: "run.missing_box_id",
      message: "boxId is required."
    });
  }
  const slot = draft.slot.trim();
  if (!/^slot\d{2}$/i.test(slot)) {
    throw new SevaUiError({
      code: "run.invalid_slot",
      message: "slot must match slotNN, for example slot01."
    });
  }
  if (!draft.modes.length) {
    throw new SevaUiError({
      code: "run.missing_modes",
      message: `Entry ${wellId} requires at least one mode.`
    });
  }

  const paramsByMode = {} as Record<ModeToken, Record<string, unknown>>;
  for (const rawToken of draft.modes) {
    const token = normalizeModeToken(rawToken);
    const rawJson = draft.modeParamsJson[token] || "{}";
    try {
      const parsed = JSON.parse(rawJson);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Mode params JSON must be an object.");
      }
      paramsByMode[token] = parsed as Record<string, unknown>;
    } catch (error) {
      throw new SevaUiError({
        code: "run.invalid_mode_params_json",
        message: `Invalid params JSON for ${token} on ${wellId}: ${(error as Error).message}`,
        cause: error
      });
    }
  }

  return {
    wellId,
    boxId,
    slot: slot.toLowerCase(),
    modes: draft.modes.map((mode) => normalizeModeToken(mode)),
    paramsByMode
  };
}

export function groupByBox(refs: RunRefDto[]): Record<string, string[]> {
  const grouped: Record<string, string[]> = {};
  for (const ref of refs) {
    if (!grouped[ref.boxId]) {
      grouped[ref.boxId] = [];
    }
    grouped[ref.boxId].push(ref.runId);
  }
  return grouped;
}
