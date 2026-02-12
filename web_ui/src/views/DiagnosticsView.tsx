import { useState } from "react";
import {
  DiscoveryResultDto,
  NasSetupDto,
  SlotStatusDto
} from "../domain/diagnostics";

interface DiagnosticsViewProps {
  boxes: string[];
  busy: boolean;
  connections: Record<string, { ok: boolean; detail: string }>;
  discoveryResults: DiscoveryResultDto[];
  rescanResults: Record<string, string[]>;
  deviceStatus: Record<string, SlotStatusDto[]>;
  nasResponse?: Record<string, unknown>;
  onRunConnectionTests: () => Promise<void>;
  onRunDiscovery: (candidateText: string) => Promise<void>;
  onRunRescan: () => Promise<void>;
  onRefreshStatus: () => Promise<void>;
  onFlashFirmware: (file: File) => Promise<void>;
  onRunNasSetup: (boxId: string, payload: NasSetupDto) => Promise<void>;
  onRunNasHealth: (boxId: string) => Promise<void>;
  onRunNasUpload: (boxId: string, runId: string) => Promise<void>;
}

const DEFAULT_NAS_SETUP: NasSetupDto = {
  host: "",
  share: "",
  username: "",
  password: "",
  base_subdir: "",
  retention_days: 14
};

export function DiagnosticsView(props: DiagnosticsViewProps) {
  const [discoveryText, setDiscoveryText] = useState("");
  const [firmwareFile, setFirmwareFile] = useState<File | undefined>(undefined);
  const [nasBoxId, setNasBoxId] = useState(props.boxes[0] || "A");
  const [nasSetup, setNasSetup] = useState<NasSetupDto>(DEFAULT_NAS_SETUP);
  const [nasUploadRunId, setNasUploadRunId] = useState("");

  return (
    <section className="stack">
      <h2>Diagnostics and Device Ops</h2>

      <div className="panel">
        <h3>Connections and status</h3>
        <div className="actions">
          <button onClick={() => void props.onRunConnectionTests()} disabled={props.busy}>
            Test configured connections
          </button>
          <button onClick={() => void props.onRunRescan()} disabled={props.busy}>
            Admin rescan
          </button>
          <button onClick={() => void props.onRefreshStatus()} disabled={props.busy}>
            Refresh device status
          </button>
        </div>
        <pre>{JSON.stringify({ connections: props.connections, rescan: props.rescanResults }, null, 2)}</pre>
        <pre>{JSON.stringify(props.deviceStatus, null, 2)}</pre>
      </div>

      <div className="panel">
        <h3>Discovery</h3>
        <p>One base URL per line. The scan runs health/version/devices probes.</p>
        <textarea
          rows={4}
          value={discoveryText}
          onChange={(event) => setDiscoveryText(event.target.value)}
          placeholder="https://box-a.example:8000&#10;https://box-b.example:8000"
        />
        <div className="actions">
          <button onClick={() => void props.onRunDiscovery(discoveryText)} disabled={props.busy}>
            Scan candidates
          </button>
        </div>
        <pre>{JSON.stringify(props.discoveryResults, null, 2)}</pre>
      </div>

      <div className="panel">
        <h3>Firmware</h3>
        <div className="actions">
          <input
            type="file"
            accept=".bin,application/octet-stream"
            onChange={(event) => setFirmwareFile(event.target.files?.[0])}
          />
          <button
            onClick={() => firmwareFile && void props.onFlashFirmware(firmwareFile)}
            disabled={props.busy || !firmwareFile}
          >
            Flash selected file on all configured boxes
          </button>
        </div>
      </div>

      <div className="panel">
        <h3>NAS</h3>
        <div className="grid four">
          <label>
            Box
            <select value={nasBoxId} onChange={(event) => setNasBoxId(event.target.value)}>
              {props.boxes.map((box) => (
                <option key={box} value={box}>
                  {box}
                </option>
              ))}
            </select>
          </label>
          <label>
            Host
            <input
              value={nasSetup.host}
              onChange={(event) => setNasSetup((current) => ({ ...current, host: event.target.value }))}
            />
          </label>
          <label>
            Share
            <input
              value={nasSetup.share}
              onChange={(event) => setNasSetup((current) => ({ ...current, share: event.target.value }))}
            />
          </label>
          <label>
            Username
            <input
              value={nasSetup.username}
              onChange={(event) => setNasSetup((current) => ({ ...current, username: event.target.value }))}
            />
          </label>
          <label>
            Password
            <input
              value={nasSetup.password}
              onChange={(event) => setNasSetup((current) => ({ ...current, password: event.target.value }))}
            />
          </label>
          <label>
            Base subdir
            <input
              value={nasSetup.base_subdir}
              onChange={(event) => setNasSetup((current) => ({ ...current, base_subdir: event.target.value }))}
            />
          </label>
          <label>
            Retention days
            <input
              type="number"
              min={0}
              value={nasSetup.retention_days}
              onChange={(event) =>
                setNasSetup((current) => ({
                  ...current,
                  retention_days: Number(event.target.value || 0)
                }))
              }
            />
          </label>
          <label>
            Domain (optional)
            <input
              value={nasSetup.domain || ""}
              onChange={(event) => setNasSetup((current) => ({ ...current, domain: event.target.value }))}
            />
          </label>
        </div>
        <div className="actions">
          <button onClick={() => void props.onRunNasSetup(nasBoxId, nasSetup)} disabled={props.busy}>
            Save NAS setup
          </button>
          <button onClick={() => void props.onRunNasHealth(nasBoxId)} disabled={props.busy}>
            Check NAS health
          </button>
        </div>
        <div className="actions">
          <label>
            Run ID for upload
            <input
              value={nasUploadRunId}
              onChange={(event) => setNasUploadRunId(event.target.value)}
              placeholder="run_id"
            />
          </label>
          <button
            onClick={() => void props.onRunNasUpload(nasBoxId, nasUploadRunId)}
            disabled={props.busy || !nasUploadRunId.trim()}
          >
            Upload run to NAS
          </button>
        </div>
        <pre>{JSON.stringify(props.nasResponse || {}, null, 2)}</pre>
      </div>
    </section>
  );
}
