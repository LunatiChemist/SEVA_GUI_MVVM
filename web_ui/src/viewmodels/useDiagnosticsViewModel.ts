import { useMemo, useState } from "react";
import { WebSettingsDto } from "../domain/settings";
import {
  DiscoveryCandidateDto,
  DiscoveryResultDto,
  NasSetupDto,
  SlotStatusDto
} from "../domain/diagnostics";
import { asTechnicalError, TechnicalError } from "../domain/errors";
import { SevaApiAdapter } from "../adapters/http/sevaApiAdapter";
import {
  checkNasHealth,
  configureNas,
  discoverCandidates,
  flashFirmwareAll,
  refreshDeviceStatus,
  rescanConfiguredBoxes,
  testConfiguredConnections,
  uploadRunToNas
} from "../services/diagnosticsService";

function parseCandidates(text: string): DiscoveryCandidateDto[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => ({ baseUrl: line }));
}

export interface DiagnosticsViewModel {
  isBusy: boolean;
  error?: TechnicalError;
  info?: string;
  connections: Record<string, { ok: boolean; detail: string }>;
  discoveryResults: DiscoveryResultDto[];
  rescanResults: Record<string, string[]>;
  deviceStatus: Record<string, SlotStatusDto[]>;
  nasResponse?: Record<string, unknown>;
  runConnectionTests: () => Promise<void>;
  runDiscovery: (candidateText: string) => Promise<void>;
  runRescan: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  flashFirmware: (file: File) => Promise<void>;
  runNasSetup: (boxId: string, request: NasSetupDto) => Promise<void>;
  runNasHealth: (boxId: string) => Promise<void>;
  runNasUpload: (boxId: string, runId: string) => Promise<void>;
}

export function useDiagnosticsViewModel(settings: WebSettingsDto): DiagnosticsViewModel {
  const adapter = useMemo(() => new SevaApiAdapter(settings), [settings]);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<TechnicalError | undefined>(undefined);
  const [info, setInfo] = useState<string | undefined>(undefined);
  const [connections, setConnections] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const [discoveryResults, setDiscoveryResults] = useState<DiscoveryResultDto[]>([]);
  const [rescanResults, setRescanResults] = useState<Record<string, string[]>>({});
  const [deviceStatus, setDeviceStatus] = useState<Record<string, SlotStatusDto[]>>({});
  const [nasResponse, setNasResponse] = useState<Record<string, unknown> | undefined>(undefined);

  const runConnectionTests = async (): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await testConfiguredConnections(adapter);
      setConnections(result);
      setInfo(`Connection tests complete for ${Object.keys(result).length} boxes.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const runDiscovery = async (candidateText: string): Promise<void> => {
    setIsBusy(true);
    try {
      const candidates = parseCandidates(candidateText);
      const result = await discoverCandidates(candidates);
      setDiscoveryResults(result);
      setInfo(`Discovery scanned ${candidates.length} candidate URLs.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const runRescan = async (): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await rescanConfiguredBoxes(adapter);
      setRescanResults(result);
      setInfo(`Rescan complete for ${Object.keys(result).length} boxes.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const refreshStatus = async (): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await refreshDeviceStatus(adapter);
      setDeviceStatus(result);
      setInfo(`Device status loaded for ${Object.keys(result).length} boxes.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const flashFirmware = async (file: File): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await flashFirmwareAll(adapter, file);
      setInfo(`Firmware flash completed for ${Object.keys(result).length} boxes.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const runNasSetup = async (boxId: string, request: NasSetupDto): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await configureNas(adapter, boxId, request);
      setNasResponse(result);
      setInfo(`NAS setup updated for box ${boxId}.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const runNasHealth = async (boxId: string): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await checkNasHealth(adapter, boxId);
      setNasResponse(result);
      setInfo(`NAS health loaded for box ${boxId}.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  const runNasUpload = async (boxId: string, runId: string): Promise<void> => {
    setIsBusy(true);
    try {
      const result = await uploadRunToNas(adapter, boxId, runId);
      setNasResponse(result);
      setInfo(`NAS upload triggered for ${runId} on ${boxId}.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setIsBusy(false);
    }
  };

  return {
    isBusy,
    error,
    info,
    connections,
    discoveryResults,
    rescanResults,
    deviceStatus,
    nasResponse,
    runConnectionTests,
    runDiscovery,
    runRescan,
    refreshStatus,
    flashFirmware,
    runNasSetup,
    runNasHealth,
    runNasUpload
  };
}
