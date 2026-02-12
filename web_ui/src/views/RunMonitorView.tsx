import { GroupHistoryItem } from "../viewmodels/useRunWorkflowViewModel";
import { RunGroupSnapshot } from "../domain/run";

interface RunMonitorViewProps {
  history: GroupHistoryItem[];
  activeGroup?: GroupHistoryItem;
  activeSnapshot?: RunGroupSnapshot;
  selectedRunIds: string[];
  autoPolling: boolean;
  busy: boolean;
  onSelectGroup: (groupId: string) => void;
  onSetSelectedRunIds: (runIds: string[]) => void;
  onPollNow: () => Promise<void>;
  onToggleAutoPolling: (enabled: boolean) => void;
  onCancelGroup: () => Promise<void>;
  onCancelSelected: () => Promise<void>;
  onDownloadGroup: () => Promise<void>;
}

export function RunMonitorView(props: RunMonitorViewProps) {
  const statuses = props.activeSnapshot?.statuses || [];

  const toggleRun = (runId: string, checked: boolean): void => {
    const next = checked
      ? [...props.selectedRunIds, runId]
      : props.selectedRunIds.filter((item) => item !== runId);
    props.onSetSelectedRunIds(Array.from(new Set(next)));
  };

  return (
    <section className="stack">
      <div className="header-line">
        <h2>Run Monitor</h2>
        <div className="actions">
          <button onClick={() => void props.onPollNow()} disabled={props.busy || !props.activeGroup}>
            Poll now
          </button>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={props.autoPolling}
              onChange={(event) => props.onToggleAutoPolling(event.target.checked)}
            />
            Auto poll
          </label>
          <button onClick={() => void props.onCancelGroup()} disabled={props.busy || !props.activeGroup}>
            Cancel group
          </button>
          <button
            onClick={() => void props.onCancelSelected()}
            disabled={props.busy || props.selectedRunIds.length === 0}
          >
            Cancel selected
          </button>
          <button onClick={() => void props.onDownloadGroup()} disabled={props.busy || !props.activeGroup}>
            Download group
          </button>
        </div>
      </div>

      <div className="panel">
        <h3>Group history</h3>
        <div className="chip-list">
          {props.history.map((item) => (
            <button
              key={item.groupId}
              className={`chip ${props.activeGroup?.groupId === item.groupId ? "active" : ""}`}
              onClick={() => props.onSelectGroup(item.groupId)}
            >
              {item.groupId}
            </button>
          ))}
          {props.history.length === 0 ? <span>No groups started yet.</span> : null}
        </div>
      </div>

      <div className="panel">
        <h3>
          Active group: <code>{props.activeGroup?.groupId || "-"}</code>
        </h3>
        <table className="table">
          <thead>
            <tr>
              <th></th>
              <th>Run ID</th>
              <th>Box</th>
              <th>Well</th>
              <th>Slot</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Remaining (s)</th>
              <th>Current mode</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {statuses.map((status) => (
              <tr key={`${status.boxId}-${status.runId}`}>
                <td>
                  <input
                    type="checkbox"
                    checked={props.selectedRunIds.includes(status.runId)}
                    onChange={(event) => toggleRun(status.runId, event.target.checked)}
                  />
                </td>
                <td>{status.runId}</td>
                <td>{status.boxId}</td>
                <td>{status.wellId || "-"}</td>
                <td>{status.slot || "-"}</td>
                <td>{status.status}</td>
                <td>{Math.round(status.progressPct)}%</td>
                <td>{typeof status.remainingS === "number" ? status.remainingS : "-"}</td>
                <td>{status.currentMode || "-"}</td>
                <td className="error-cell">{status.errorMessage || "-"}</td>
              </tr>
            ))}
            {statuses.length === 0 ? (
              <tr>
                <td colSpan={10}>No status data loaded for active group.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
