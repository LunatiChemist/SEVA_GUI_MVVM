import { SevaApiAdapter } from "../adapters/http/sevaApiAdapter";
import { TemperatureSampleDto } from "../domain/telemetry";

export async function fetchLatestTelemetry(
  adapter: SevaApiAdapter,
  boxId: string
): Promise<TemperatureSampleDto[]> {
  const payload = await adapter.telemetryLatest(boxId);
  return payload.samples;
}

export function startTelemetryStream(
  adapter: SevaApiAdapter,
  boxId: string,
  rateHz: number,
  onSample: (sample: TemperatureSampleDto) => void,
  onError: (message: string) => void
): () => void {
  const source = new EventSource(adapter.telemetryStreamUrl(boxId, rateHz));
  source.addEventListener("temp", (event) => {
    try {
      const sample = JSON.parse((event as MessageEvent).data) as TemperatureSampleDto;
      onSample(sample);
    } catch (error) {
      onError((error as Error).message);
    }
  });
  source.onerror = () => {
    onError("Telemetry stream disconnected.");
  };
  return () => source.close();
}
