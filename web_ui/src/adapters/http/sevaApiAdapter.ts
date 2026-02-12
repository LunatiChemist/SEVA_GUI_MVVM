import { HttpClient } from "./httpClient";
import {
  BoxConnectionDto,
  WebSettingsDto,
  configuredBoxes
} from "../../domain/settings";
import {
  DevicesDto,
  HealthDto,
  NasSetupDto,
  SlotStatusDto,
  VersionDto
} from "../../domain/diagnostics";
import {
  JobStatusApi,
  StartJobApiResponse
} from "../../domain/run";
import { LatestTelemetryDto } from "../../domain/telemetry";
import { ModeToken } from "../../domain/modeRegistry";
import { SevaUiError } from "../../domain/errors";

export interface ValidateModeResult {
  ok: boolean;
  errors: Array<{
    field: string;
    code: string;
    message: string;
  }>;
  warnings: Array<{
    field: string;
    code: string;
    message: string;
  }>;
}

export interface StartJobRequest {
  devices: string[];
  modes: string[];
  params_by_mode: Record<string, Record<string, unknown>>;
  tia_gain?: number;
  sampling_interval?: number;
  experiment_name: string;
  subdir?: string;
  client_datetime: string;
  group_id: string;
  make_plot: boolean;
}

export class SevaApiAdapter {
  private readonly settings: WebSettingsDto;

  constructor(settings: WebSettingsDto) {
    this.settings = settings;
  }

  configuredBoxes(): BoxConnectionDto[] {
    return configuredBoxes(this.settings);
  }

  getBox(boxId: string): BoxConnectionDto {
    const box = this.settings.boxes.find((item) => item.boxId === boxId);
    if (!box || !box.baseUrl.trim()) {
      throw new SevaUiError({
        code: "settings.box_not_configured",
        message: `No configured box URL for ${boxId}.`
      });
    }
    return box;
  }

  async getHealth(boxId: string): Promise<HealthDto> {
    return this.clientFor(boxId).requestJson<HealthDto>({
      path: "/health",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async getVersion(boxId: string): Promise<VersionDto> {
    return this.clientFor(boxId).requestJson<VersionDto>({
      path: "/version",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async getDevices(boxId: string): Promise<DevicesDto> {
    return this.clientFor(boxId).requestJson<DevicesDto>({
      path: "/devices",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async getDeviceStatus(boxId: string): Promise<SlotStatusDto[]> {
    return this.clientFor(boxId).requestJson<SlotStatusDto[]>({
      path: "/devices/status",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async listModes(boxId: string): Promise<string[]> {
    return this.clientFor(boxId).requestJson<string[]>({
      path: "/modes",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async modeParams(boxId: string, mode: ModeToken): Promise<Record<string, string>> {
    return this.clientFor(boxId).requestJson<Record<string, string>>({
      path: `/modes/${mode}/params`,
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async validateMode(
    boxId: string,
    mode: ModeToken,
    params: Record<string, unknown>
  ): Promise<ValidateModeResult> {
    return this.clientFor(boxId).requestJson<ValidateModeResult>({
      method: "POST",
      path: `/modes/${mode}/validate`,
      body: params,
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async startJob(boxId: string, request: StartJobRequest): Promise<StartJobApiResponse> {
    return this.clientFor(boxId).requestJson<StartJobApiResponse>({
      method: "POST",
      path: "/jobs",
      body: request,
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async pollJobs(boxId: string, runIds: string[]): Promise<JobStatusApi[]> {
    return this.clientFor(boxId).requestJson<JobStatusApi[]>({
      method: "POST",
      path: "/jobs/status",
      body: { run_ids: runIds },
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async cancelJob(boxId: string, runId: string): Promise<{ run_id: string; status: string }> {
    return this.clientFor(boxId).requestJson<{ run_id: string; status: string }>({
      method: "POST",
      path: `/jobs/${encodeURIComponent(runId)}/cancel`,
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async downloadRunZip(boxId: string, runId: string): Promise<Blob> {
    return this.clientFor(boxId).requestBlob({
      path: `/runs/${encodeURIComponent(runId)}/zip`,
      timeoutMs: this.settings.downloadTimeoutS * 1000
    });
  }

  async rescanDevices(boxId: string): Promise<{ devices: string[] }> {
    return this.clientFor(boxId).requestJson<{ devices: string[] }>({
      method: "POST",
      path: "/admin/rescan",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async flashFirmware(boxId: string, file: File): Promise<Record<string, unknown>> {
    const box = this.getBox(boxId);
    const formData = new FormData();
    formData.append("file", file);
    const headers = new Headers();
    if (box.apiKey) {
      headers.set("X-API-Key", box.apiKey);
    }

    const response = await fetch(`${box.baseUrl.replace(/\/+$/, "")}/firmware/flash`, {
      method: "POST",
      body: formData,
      headers
    });

    if (!response.ok) {
      throw new SevaUiError({
        status: response.status,
        code: "firmware.flash_failed",
        message: `Firmware flash failed for box ${boxId}.`
      });
    }

    const payload = (await response.json()) as Record<string, unknown>;
    return payload;
  }

  async nasSetup(boxId: string, request: NasSetupDto): Promise<Record<string, unknown>> {
    return this.clientFor(boxId).requestJson<Record<string, unknown>>({
      method: "POST",
      path: "/nas/setup",
      body: request,
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async nasHealth(boxId: string): Promise<Record<string, unknown>> {
    return this.clientFor(boxId).requestJson<Record<string, unknown>>({
      path: "/nas/health",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async nasUploadRun(boxId: string, runId: string): Promise<Record<string, unknown>> {
    return this.clientFor(boxId).requestJson<Record<string, unknown>>({
      method: "POST",
      path: `/runs/${encodeURIComponent(runId)}/upload`,
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  async telemetryLatest(boxId: string): Promise<LatestTelemetryDto> {
    return this.clientFor(boxId).requestJson<LatestTelemetryDto>({
      path: "/api/telemetry/temperature/latest",
      timeoutMs: this.settings.requestTimeoutS * 1000
    });
  }

  telemetryStreamUrl(boxId: string, rateHz: number): string {
    const box = this.getBox(boxId);
    const base = box.baseUrl.replace(/\/+$/, "");
    return `${base}/api/telemetry/temperature/stream?rate_hz=${rateHz}`;
  }

  private clientFor(boxId: string): HttpClient {
    const box = this.getBox(boxId);
    return new HttpClient(box, this.settings.requestTimeoutS * 1000);
  }
}
