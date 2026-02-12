import { EntryDraftState } from "../domain/run";
import { ModeToken, listModeDefinitions } from "../domain/modeRegistry";

interface RunPlannerViewProps {
  entries: EntryDraftState[];
  boxes: string[];
  busy: boolean;
  validationSummary: Record<string, string>;
  onAddEntry: () => void;
  onRemoveEntry: (index: number) => void;
  onUpdateField: (index: number, field: keyof EntryDraftState, value: string) => void;
  onToggleMode: (index: number, mode: ModeToken) => void;
  onUpdateModeJson: (index: number, mode: ModeToken, payload: string) => void;
  onValidateEntry: (index: number) => Promise<void>;
  onStart: () => Promise<void>;
}

const MODES = listModeDefinitions();

export function RunPlannerView(props: RunPlannerViewProps) {
  return (
    <section className="stack">
      <div className="header-line">
        <h2>Run Planner</h2>
        <div className="actions">
          <button onClick={props.onAddEntry} disabled={props.busy}>
            Add run entry
          </button>
          <button onClick={() => void props.onStart()} disabled={props.busy || props.entries.length === 0}>
            Start group
          </button>
        </div>
      </div>

      {props.entries.map((entry, index) => (
        <article key={`${index}-${entry.boxId}-${entry.wellId}`} className="panel run-entry">
          <div className="header-line">
            <h3>Entry {index + 1}</h3>
            <button className="ghost" onClick={() => props.onRemoveEntry(index)} disabled={props.entries.length <= 1}>
              Remove
            </button>
          </div>

          <div className="grid four">
            <label>
              Well ID
              <input
                value={entry.wellId}
                onChange={(event) => props.onUpdateField(index, "wellId", event.target.value)}
                placeholder="A1"
              />
            </label>
            <label>
              Box
              <select value={entry.boxId} onChange={(event) => props.onUpdateField(index, "boxId", event.target.value)}>
                {props.boxes.map((box) => (
                  <option key={box} value={box}>
                    {box}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Slot
              <input
                value={entry.slot}
                onChange={(event) => props.onUpdateField(index, "slot", event.target.value)}
                placeholder="slot01"
              />
            </label>
          </div>

          <div className="stack">
            <h4>Modes</h4>
            <div className="mode-list">
              {MODES.map((mode) => (
                <label key={mode.token} className="checkbox">
                  <input
                    type="checkbox"
                    checked={entry.modes.includes(mode.token)}
                    onChange={() => props.onToggleMode(index, mode.token)}
                  />
                  {mode.token} - {mode.label}
                </label>
              ))}
            </div>
          </div>

          {entry.modes.map((mode) => (
            <label key={`${index}-${mode}`} className="json-editor">
              {mode} params JSON
              <textarea
                value={entry.modeParamsJson[mode] || "{}"}
                onChange={(event) => props.onUpdateModeJson(index, mode, event.target.value)}
                rows={5}
              />
            </label>
          ))}

          <div className="actions">
            <button onClick={() => void props.onValidateEntry(index)} disabled={props.busy || entry.modes.length === 0}>
              Validate selected modes
            </button>
            <span className="hint">{props.validationSummary[String(index)] || "No validation result yet."}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
