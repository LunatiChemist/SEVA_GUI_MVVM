import { SevaApiAdapter } from "../adapters/http/sevaApiAdapter";
import {
  DiscoveryCandidateDto,
  DiscoveryResultDto,
  NasSetupDto,
  SlotStatusDto
} from "../domain/diagnostics";

export async function testConfiguredConnections(
  adapter: SevaApiAdapter
): Promise<Record<string, { ok: boolean; detail: string }>> {
  const results: Record<string, { ok: boolean; detail: string }> = {};
  for (const box of adapter.configuredBoxes()) {
    try {
      const [health, devices] = await Promise.all([
        adapter.getHealth(box.boxId),
        adapter.getDevices(box.boxId)
      ]);
      results[box.boxId] = {
        ok: true,
        detail: `ok=${health.ok} devices=${devices.count}`
      };
    } catch (error) {
      results[box.boxId] = {
        ok: false,
        detail: (error as Error).message
      };
    }
  }
  return results;
}

export async function discoverCandidates(
  candidates: DiscoveryCandidateDto[]
): Promise<DiscoveryResultDto[]> {
  const outcomes: DiscoveryResultDto[] = [];
  for (const candidate of candidates) {
    const temporaryAdapter = new SevaApiAdapter({
      version: 1,
      boxes: [{ boxId: "X", baseUrl: candidate.baseUrl, apiKey: candidate.apiKey || "" }],
      requestTimeoutS: 5,
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
    });

    try {
      const [health, version, devices] = await Promise.all([
        temporaryAdapter.getHealth("X"),
        temporaryAdapter.getVersion("X"),
        temporaryAdapter.getDevices("X")
      ]);
      outcomes.push({
        baseUrl: candidate.baseUrl,
        ok: true,
        health,
        version,
        devices
      });
    } catch (error) {
      outcomes.push({
        baseUrl: candidate.baseUrl,
        ok: false,
        error: (error as Error).message
      });
    }
  }
  return outcomes;
}

export async function rescanConfiguredBoxes(
  adapter: SevaApiAdapter
): Promise<Record<string, string[]>> {
  const results: Record<string, string[]> = {};
  for (const box of adapter.configuredBoxes()) {
    const payload = await adapter.rescanDevices(box.boxId);
    results[box.boxId] = payload.devices;
  }
  return results;
}

export async function refreshDeviceStatus(
  adapter: SevaApiAdapter
): Promise<Record<string, SlotStatusDto[]>> {
  const results: Record<string, SlotStatusDto[]> = {};
  for (const box of adapter.configuredBoxes()) {
    results[box.boxId] = await adapter.getDeviceStatus(box.boxId);
  }
  return results;
}

export async function flashFirmwareAll(
  adapter: SevaApiAdapter,
  file: File
): Promise<Record<string, Record<string, unknown>>> {
  const outcomes: Record<string, Record<string, unknown>> = {};
  for (const box of adapter.configuredBoxes()) {
    outcomes[box.boxId] = await adapter.flashFirmware(box.boxId, file);
  }
  return outcomes;
}

export async function configureNas(
  adapter: SevaApiAdapter,
  boxId: string,
  request: NasSetupDto
): Promise<Record<string, unknown>> {
  return adapter.nasSetup(boxId, request);
}

export async function checkNasHealth(
  adapter: SevaApiAdapter,
  boxId: string
): Promise<Record<string, unknown>> {
  return adapter.nasHealth(boxId);
}

export async function uploadRunToNas(
  adapter: SevaApiAdapter,
  boxId: string,
  runId: string
): Promise<Record<string, unknown>> {
  return adapter.nasUploadRun(boxId, runId);
}
