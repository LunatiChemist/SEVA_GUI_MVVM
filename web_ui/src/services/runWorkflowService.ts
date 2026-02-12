import { SevaApiAdapter } from "../adapters/http/sevaApiAdapter";
import { downloadBlob } from "../adapters/browser/fileTransfer";
import {
  EntryDraftState,
  RunGroupSnapshot,
  RunRefDto,
  RunStatusDto,
  StartGroupCommand,
  createEmptyEntry,
  groupByBox,
  normalizeEntryDraft
} from "../domain/run";
import { ModeToken } from "../domain/modeRegistry";

export interface BuildGroupCommandInput {
  experimentName: string;
  subdir?: string;
  entries: EntryDraftState[];
}

const TERMINAL_STATUSES = new Set(["done", "failed", "cancelled", "canceled"]);

export function createDefaultDraftEntries(): EntryDraftState[] {
  return [createEmptyEntry("A")];
}

export function buildStartGroupCommand(input: BuildGroupCommandInput): StartGroupCommand {
  const entries = input.entries.map((entry) => normalizeEntryDraft(entry));
  const timestamp = new Date().toISOString();
  const stamp = timestamp.replace(/[-:]/g, "").replace(/\..+/, "");
  return {
    groupId: `web_${stamp}`,
    clientDateTime: timestamp,
    experimentName: input.experimentName.trim() || "web-experiment",
    subdir: input.subdir?.trim() || undefined,
    entries
  };
}

export async function startGroup(
  adapter: SevaApiAdapter,
  command: StartGroupCommand
): Promise<RunRefDto[]> {
  const refs: RunRefDto[] = [];
  for (const entry of command.entries) {
    const response = await adapter.startJob(entry.boxId, {
      devices: [entry.slot],
      modes: entry.modes,
      params_by_mode: entry.paramsByMode,
      experiment_name: command.experimentName,
      subdir: command.subdir,
      client_datetime: command.clientDateTime,
      group_id: command.groupId,
      make_plot: true
    });
    refs.push({
      groupId: command.groupId,
      boxId: entry.boxId,
      runId: response.run_id,
      wellId: entry.wellId,
      slot: entry.slot
    });
  }
  return refs;
}

export async function pollGroup(
  adapter: SevaApiAdapter,
  refs: RunRefDto[]
): Promise<RunGroupSnapshot> {
  const grouped = groupByBox(refs);
  const statuses: RunStatusDto[] = [];
  for (const [boxId, runIds] of Object.entries(grouped)) {
    const response = await adapter.pollJobs(boxId, runIds);
    for (const job of response) {
      const source = refs.find((item) => item.runId === job.run_id && item.boxId === boxId);
      const slot = job.slots?.[0];
      statuses.push({
        runId: job.run_id,
        boxId,
        status: (job.status || "queued").toLowerCase(),
        startedAt: job.started_at,
        endedAt: job.ended_at,
        progressPct: Number(job.progress_pct || 0),
        remainingS: typeof job.remaining_s === "number" ? job.remaining_s : undefined,
        currentMode: job.current_mode || job.mode,
        remainingModes: Array.isArray(job.remaining_modes) ? job.remaining_modes : [],
        errorMessage: slot?.message,
        wellId: source?.wellId,
        slot: source?.slot
      });
    }
  }

  return {
    groupId: refs[0]?.groupId || "",
    statuses,
    allDone: statuses.length > 0 && statuses.every((item) => TERMINAL_STATUSES.has(item.status)),
    polledAt: new Date().toISOString()
  };
}

export async function cancelGroup(adapter: SevaApiAdapter, refs: RunRefDto[]): Promise<void> {
  await cancelRuns(adapter, refs);
}

export async function cancelRuns(adapter: SevaApiAdapter, refs: RunRefDto[]): Promise<void> {
  for (const ref of refs) {
    await adapter.cancelJob(ref.boxId, ref.runId);
  }
}

export async function downloadGroup(adapter: SevaApiAdapter, refs: RunRefDto[]): Promise<void> {
  for (const ref of refs) {
    const blob = await adapter.downloadRunZip(ref.boxId, ref.runId);
    downloadBlob(`${ref.groupId}_${ref.boxId}_${ref.runId}.zip`, blob);
  }
}

export async function validateModes(
  adapter: SevaApiAdapter,
  entry: EntryDraftState
): Promise<Record<ModeToken, { ok: boolean; errorCount: number; warningCount: number }>> {
  const normalized = normalizeEntryDraft(entry);
  const summary = {} as Record<
    ModeToken,
    { ok: boolean; errorCount: number; warningCount: number }
  >;

  for (const mode of normalized.modes) {
    const validation = await adapter.validateMode(
      normalized.boxId,
      mode,
      normalized.paramsByMode[mode]
    );
    summary[mode] = {
      ok: validation.ok,
      errorCount: validation.errors.length,
      warningCount: validation.warnings.length
    };
  }
  return summary;
}
