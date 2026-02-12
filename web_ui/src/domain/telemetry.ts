export interface TemperatureSampleDto {
  device_id: number;
  ts: string;
  temp_c: number;
  seq: number;
}

export interface LatestTelemetryDto {
  samples: TemperatureSampleDto[];
}
