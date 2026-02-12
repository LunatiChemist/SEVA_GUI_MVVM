import { useEffect, useMemo, useState } from "react";
import { WebSettingsDto } from "../domain/settings";
import {
  EntryDraftState,
  RunGroupSnapshot,
  RunRefDto,
  createEmptyEntry
} from "../domain/run";
import { ModeToken } from "../domain/modeRegistry";
import { asTechnicalError, TechnicalError } from "../domain/errors";
import { SevaApiAdapter } from "../adapters/http/sevaApiAdapter";
import {
  buildStartGroupCommand,
  cancelGroup,
  cancelRuns,
  downloadGroup,
  pollGroup,
  startGroup,
  validateModes
} from "../services/runWorkflowService";

export interface GroupHistoryItem {
  groupId: string;
  refs: RunRefDto[];
  lastSnapshot?: RunGroupSnapshot;
}

export interface RunWorkflowViewModel {
  entries: EntryDraftState[];
  groupHistory: GroupHistoryItem[];
  activeGroup?: GroupHistoryItem;
  activeSnapshot?: RunGroupSnapshot;
  isBusy: boolean;
  autoPolling: boolean;
  selectedRunIds: string[];
  validationSummary: Record<string, string>;
  error?: TechnicalError;
  info?: string;
  addEntry: () => void;
  removeEntry: (index: number) => void;
  updateEntryField: (index: number, field: keyof EntryDraftState, value: string) => void;
  toggleMode: (index: number, mode: ModeToken) => void;
  updateModeJson: (index: number, mode: ModeToken, payload: string) => void;
  validateEntryModes: (index: number) => Promise<void>;
  start: (experimentName: string, subdir?: string) => Promise<void>;
  pollNow: () => Promise<void>;
  setAutoPolling: (enabled: boolean) => void;
  setSelectedRunIds: (runIds: string[]) => void;
  cancelActiveGroup: () => Promise<void>;
  cancelSelectedRuns: () => Promise<void>;
  downloadActiveGroup: () => Promise<void>;
  setActiveGroup: (groupId: string) => void;
}

export function useRunWorkflowViewModel(settings: WebSettingsDto): RunWorkflowViewModel {
  const [entries, setEntries] = useState<EntryDraftState[]>([createEmptyEntry("A")]);
  const [groupHistory, setGroupHistory] = useState<GroupHistoryItem[]>([]);
  const [activeGroupId, setActiveGroupId] = useState<string | undefined>(undefined);
  const [activeSnapshot, setActiveSnapshot] = useState<RunGroupSnapshot | undefined>(undefined);
  const [isBusy, setIsBusy] = useState(false);
  const [autoPolling, setAutoPolling] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [validationSummary, setValidationSummary] = useState<Record<string, string>>({});
  const [error, setError] = useState<TechnicalError | undefined>(undefined);
  const [info, setInfo] = useState<string | undefined>(undefined);
  const adapter = useMemo(() => new SevaApiAdapter(settings), [settings]);

  const activeGroup = useMemo(
    () => groupHistory.find((item) => item.groupId === activeGroupId),
    [activeGroupId, groupHistory]
  );

  useEffect(() => {
    setSelectedRunIds([]);
    if (activeGroup?.lastSnapshot) {
      setActiveSnapshot(activeGroup.lastSnapshot);
      return;
    }
    setActiveSnapshot(undefined);
  }, [activeGroup]);

  useEffect(() => {
    if (!autoPolling || !activeGroup || isBusy) {
      return;
    }
    const interval = Math.max(200, settings.pollIntervalMs);
    const handle = window.setInterval(() => {
      void pollNow();
    }, interval);
    return () => window.clearInterval(handle);
  }, [autoPolling, activeGroup, isBusy, settings.pollIntervalMs]);

  const addEntry = (): void => {
    const fallbackBox = settings.boxes[0]?.boxId || "A";
    setEntries((current) => [...current, createEmptyEntry(fallbackBox)]);
  };

  const removeEntry = (index: number): void => {
    setEntries((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const updateEntryField = (
    index: number,
    field: keyof EntryDraftState,
    value: string
  ): void => {
    setEntries((current) =>
      current.map((entry, itemIndex) =>
        itemIndex === index
          ? {
              ...entry,
              [field]: value
            }
          : entry
      )
    );
  };

  const toggleMode = (index: number, mode: ModeToken): void => {
    setEntries((current) =>
      current.map((entry, itemIndex) => {
        if (itemIndex !== index) {
          return entry;
        }
        const exists = entry.modes.includes(mode);
        if (exists) {
          const nextModes = entry.modes.filter((item) => item !== mode);
          return { ...entry, modes: nextModes };
        }
        return {
          ...entry,
          modes: [...entry.modes, mode],
          modeParamsJson: {
            ...entry.modeParamsJson,
            [mode]: entry.modeParamsJson[mode] || "{}"
          }
        };
      })
    );
  };

  const updateModeJson = (index: number, mode: ModeToken, payload: string): void => {
    setEntries((current) =>
      current.map((entry, itemIndex) =>
        itemIndex === index
          ? {
              ...entry,
              modeParamsJson: {
                ...entry.modeParamsJson,
                [mode]: payload
              }
            }
          : entry
      )
    );
  };

  const validateEntryModes = async (index: number): Promise<void> => {
    setIsBusy(true);
    try {
      const entry = entries[index];
      const summary = await validateModes(adapter, entry);
      const key = `${index}`;
      const fragments = Object.entries(summary).map(
        ([mode, state]) =>
          `${mode}: ok=${state.ok} errors=${state.errorCount} warnings=${state.warningCount}`
      );
      setValidationSummary((current) => ({
        ...current,
        [key]: fragments.join(" | ")
      }));
      setInfo(`Validation complete for entry ${index + 1}.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const start = async (experimentName: string, subdir?: string): Promise<void> => {
    setIsBusy(true);
    try {
      const command = buildStartGroupCommand({ experimentName, subdir, entries });
      const refs = await startGroup(adapter, command);
      const item: GroupHistoryItem = { groupId: command.groupId, refs };
      setGroupHistory((current) => [item, ...current]);
      setActiveGroupId(command.groupId);
      setSelectedRunIds([]);
      setInfo(`Started group ${command.groupId} with ${refs.length} runs.`);
      setError(undefined);
      if (settings.autoDownloadOnComplete) {
        setAutoPolling(true);
      }
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const pollNow = async (): Promise<void> => {
    if (!activeGroup) {
      return;
    }
    setIsBusy(true);
    try {
      const snapshot = await pollGroup(adapter, activeGroup.refs);
      setActiveSnapshot(snapshot);
      setGroupHistory((current) =>
        current.map((item) =>
          item.groupId === activeGroup.groupId
            ? {
                ...item,
                lastSnapshot: snapshot
              }
            : item
        )
      );
      setInfo(`Polled ${snapshot.statuses.length} runs at ${snapshot.polledAt}.`);
      setError(undefined);
      if (snapshot.allDone && settings.autoDownloadOnComplete) {
        await downloadGroup(adapter, activeGroup.refs);
        setInfo(`Group ${activeGroup.groupId} completed and downloads were triggered.`);
        setAutoPolling(false);
      }
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const cancelActiveGroup = async (): Promise<void> => {
    if (!activeGroup) {
      return;
    }
    setIsBusy(true);
    try {
      await cancelGroup(adapter, activeGroup.refs);
      setInfo(`Cancel requested for group ${activeGroup.groupId}.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const cancelSelectedRuns = async (): Promise<void> => {
    if (!activeGroup || selectedRunIds.length === 0) {
      return;
    }
    setIsBusy(true);
    try {
      const refs = activeGroup.refs.filter((item) => selectedRunIds.includes(item.runId));
      await cancelRuns(adapter, refs);
      setInfo(`Cancel requested for ${refs.length} selected runs.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const downloadActiveGroup = async (): Promise<void> => {
    if (!activeGroup) {
      return;
    }
    setIsBusy(true);
    try {
      await downloadGroup(adapter, activeGroup.refs);
      setInfo(`Download triggered for group ${activeGroup.groupId}.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  return {
    entries,
    groupHistory,
    activeGroup,
    activeSnapshot,
    isBusy,
    autoPolling,
    selectedRunIds,
    validationSummary,
    error,
    info,
    addEntry,
    removeEntry,
    updateEntryField,
    toggleMode,
    updateModeJson,
    validateEntryModes,
    start,
    pollNow,
    setAutoPolling,
    setSelectedRunIds,
    cancelActiveGroup,
    cancelSelectedRuns,
    downloadActiveGroup,
    setActiveGroup: (groupId: string) => setActiveGroupId(groupId)
  };
}
