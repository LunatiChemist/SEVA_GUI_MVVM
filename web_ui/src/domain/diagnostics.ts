export interface HealthDto {
  ok: boolean;
  devices: number;
  box_id?: string;
}

export interface VersionDto {
  api: string;
  pybeep: string;
  python: string;
  build: string;
}

export interface DevicesDto {
  devices: Array<{
    slot: string;
    port?: string;
    sn?: string;
  }>;
  slots: string[];
  count: number;
}

export interface SlotStatusDto {
  slot: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  message?: string;
}

export interface DiscoveryCandidateDto {
  baseUrl: string;
  apiKey?: string;
}

export interface DiscoveryResultDto {
  baseUrl: string;
  ok: boolean;
  health?: HealthDto;
  version?: VersionDto;
  devices?: DevicesDto;
  error?: string;
}

export interface NasSetupDto {
  host: string;
  share: string;
  username: string;
  password: string;
  base_subdir: string;
  retention_days: number;
  domain?: string;
}
