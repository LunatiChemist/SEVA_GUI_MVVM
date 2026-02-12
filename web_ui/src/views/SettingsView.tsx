import { ChangeEvent } from "react";
import { WebSettingsDto } from "../domain/settings";

interface SettingsViewProps {
  settings: WebSettingsDto;
  savedAt?: string;
  loading: boolean;
  onUpdateBox: (boxId: string, field: "baseUrl" | "apiKey", value: string) => void;
  onUpdateField: <K extends keyof WebSettingsDto>(field: K, value: WebSettingsDto[K]) => void;
  onSave: () => void;
  onExport: () => void;
  onImport: (file: File) => Promise<void>;
  onReset: () => void;
}

function asNumber(value: string): number {
  return Number(value || 0);
}

export function SettingsView(props: SettingsViewProps) {
  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await props.onImport(file);
    event.target.value = "";
  };

  return (
    <section className="stack">
      <h2>Settings</h2>
      <div className="panel">
        <h3>Boxes</h3>
        <div className="grid two">
          {props.settings.boxes.map((box) => (
            <div key={box.boxId} className="row-card">
              <h4>Box {box.boxId}</h4>
              <label>
                Base URL
                <input
                  value={box.baseUrl}
                  onChange={(event) => props.onUpdateBox(box.boxId, "baseUrl", event.target.value)}
                  placeholder="https://example-host:8000"
                />
              </label>
              <label>
                API Key (optional)
                <input
                  value={box.apiKey}
                  onChange={(event) => props.onUpdateBox(box.boxId, "apiKey", event.target.value)}
                />
              </label>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>Timing</h3>
        <div className="grid four">
          <label>
            Request timeout (s)
            <input
              type="number"
              min={1}
              value={props.settings.requestTimeoutS}
              onChange={(event) => props.onUpdateField("requestTimeoutS", asNumber(event.target.value))}
            />
          </label>
          <label>
            Download timeout (s)
            <input
              type="number"
              min={1}
              value={props.settings.downloadTimeoutS}
              onChange={(event) => props.onUpdateField("downloadTimeoutS", asNumber(event.target.value))}
            />
          </label>
          <label>
            Poll interval (ms)
            <input
              type="number"
              min={100}
              value={props.settings.pollIntervalMs}
              onChange={(event) => props.onUpdateField("pollIntervalMs", asNumber(event.target.value))}
            />
          </label>
          <label>
            Poll backoff max (ms)
            <input
              type="number"
              min={100}
              value={props.settings.pollBackoffMaxMs}
              onChange={(event) => props.onUpdateField("pollBackoffMaxMs", asNumber(event.target.value))}
            />
          </label>
        </div>
      </div>

      <div className="panel">
        <h3>Storage and defaults</h3>
        <div className="grid two">
          <label>
            Results directory label
            <input
              value={props.settings.resultsDir}
              onChange={(event) => props.onUpdateField("resultsDir", event.target.value)}
            />
          </label>
          <label>
            Experiment name
            <input
              value={props.settings.experimentName}
              onChange={(event) => props.onUpdateField("experimentName", event.target.value)}
            />
          </label>
          <label>
            Subdirectory
            <input
              value={props.settings.subdir}
              onChange={(event) => props.onUpdateField("subdir", event.target.value)}
            />
          </label>
          <label>
            Relay IP
            <input
              value={props.settings.relayIp}
              onChange={(event) => props.onUpdateField("relayIp", event.target.value)}
            />
          </label>
          <label>
            Relay Port
            <input
              type="number"
              min={0}
              value={props.settings.relayPort}
              onChange={(event) => props.onUpdateField("relayPort", asNumber(event.target.value))}
            />
          </label>
          <label>
            Firmware path hint
            <input
              value={props.settings.firmwarePathHint}
              onChange={(event) => props.onUpdateField("firmwarePathHint", event.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="panel">
        <h3>Flags</h3>
        <div className="grid two">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={props.settings.autoDownloadOnComplete}
              onChange={(event) => props.onUpdateField("autoDownloadOnComplete", event.target.checked)}
            />
            Auto-download on complete
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={props.settings.useStreaming}
              onChange={(event) => props.onUpdateField("useStreaming", event.target.checked)}
            />
            Use streaming for telemetry
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={props.settings.debugLogging}
              onChange={(event) => props.onUpdateField("debugLogging", event.target.checked)}
            />
            Enable debug logging
          </label>
        </div>
      </div>

      <div className="panel">
        <h3>Import / Export</h3>
        <div className="actions">
          <button onClick={props.onSave} disabled={props.loading}>
            Save to browser
          </button>
          <button onClick={props.onExport} disabled={props.loading}>
            Export JSON
          </button>
          <label className="import-button">
            Import JSON
            <input type="file" accept="application/json" onChange={handleImport} />
          </label>
          <button className="ghost" onClick={props.onReset} disabled={props.loading}>
            Reset to defaults
          </button>
        </div>
        {props.savedAt ? <p>Last saved: {props.savedAt}</p> : <p>No local save yet.</p>}
      </div>
    </section>
  );
}
