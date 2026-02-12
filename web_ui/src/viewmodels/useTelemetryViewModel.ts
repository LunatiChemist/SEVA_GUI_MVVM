import { useEffect, useMemo, useState } from "react";
import { WebSettingsDto } from "../domain/settings";
import { TemperatureSampleDto } from "../domain/telemetry";
import { asTechnicalError, TechnicalError } from "../domain/errors";
import { SevaApiAdapter } from "../adapters/http/sevaApiAdapter";
import {
  fetchLatestTelemetry,
  startTelemetryStream
} from "../services/telemetryService";

const MAX_SAMPLES = 80;

export interface TelemetryViewModel {
  boxId: string;
  samples: TemperatureSampleDto[];
  isStreaming: boolean;
  error?: TechnicalError;
  info?: string;
  setBoxId: (boxId: string) => void;
  refresh: () => Promise<void>;
  setStreaming: (enabled: boolean) => void;
}

export function useTelemetryViewModel(settings: WebSettingsDto): TelemetryViewModel {
  const fallback = settings.boxes[0]?.boxId || "A";
  const [boxId, setBoxId] = useState(fallback);
  const [samples, setSamples] = useState<TemperatureSampleDto[]>([]);
  const [isStreaming, setStreaming] = useState(false);
  const [error, setError] = useState<TechnicalError | undefined>(undefined);
  const [info, setInfo] = useState<string | undefined>(undefined);
  const adapter = useMemo(() => new SevaApiAdapter(settings), [settings]);

  useEffect(() => {
    if (!isStreaming) {
      return;
    }
    const stop = startTelemetryStream(
      adapter,
      boxId,
      2,
      (sample) => {
        setSamples((current) => [sample, ...current].slice(0, MAX_SAMPLES));
      },
      (message) => {
        setError({
          code: "telemetry.stream_error",
          message
        });
      }
    );
    return stop;
  }, [adapter, boxId, isStreaming]);

  const refresh = async (): Promise<void> => {
    try {
      const payload = await fetchLatestTelemetry(adapter, boxId);
      setSamples(payload.slice().reverse());
      setInfo(`Loaded ${payload.length} telemetry samples.`);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    }
  };

  return {
    boxId,
    samples,
    isStreaming,
    error,
    info,
    setBoxId,
    refresh,
    setStreaming
  };
}
