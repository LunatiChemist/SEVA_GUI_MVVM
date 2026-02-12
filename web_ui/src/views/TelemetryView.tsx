import { TemperatureSampleDto } from "../domain/telemetry";

interface TelemetryViewProps {
  boxes: string[];
  selectedBoxId: string;
  samples: TemperatureSampleDto[];
  streaming: boolean;
  busy: boolean;
  onSelectBox: (boxId: string) => void;
  onRefresh: () => Promise<void>;
  onStreamingChange: (enabled: boolean) => void;
}

export function TelemetryView(props: TelemetryViewProps) {
  return (
    <section className="stack">
      <h2>Telemetry and Data Plotter Entry</h2>
      <p>
        This tab provides the browser-side telemetry entrypoint. Run lifecycle status still comes from job polling,
        and this stream is a supplemental diagnostics/plotting channel.
      </p>

      <div className="panel">
        <div className="actions">
          <label>
            Box
            <select value={props.selectedBoxId} onChange={(event) => props.onSelectBox(event.target.value)}>
              {props.boxes.map((box) => (
                <option key={box} value={box}>
                  {box}
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => void props.onRefresh()} disabled={props.busy}>
            Load latest snapshot
          </button>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={props.streaming}
              onChange={(event) => props.onStreamingChange(event.target.checked)}
            />
            Stream telemetry (SSE)
          </label>
        </div>

        <table className="table">
          <thead>
            <tr>
              <th>Device</th>
              <th>Timestamp</th>
              <th>Temperature (C)</th>
              <th>Seq</th>
            </tr>
          </thead>
          <tbody>
            {props.samples.map((sample) => (
              <tr key={`${sample.device_id}-${sample.seq}`}>
                <td>{sample.device_id}</td>
                <td>{sample.ts}</td>
                <td>{sample.temp_c}</td>
                <td>{sample.seq}</td>
              </tr>
            ))}
            {props.samples.length === 0 ? (
              <tr>
                <td colSpan={4}>No telemetry samples loaded.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
