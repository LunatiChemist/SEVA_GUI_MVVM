import { useMemo, useState } from "react";
import { SettingsView } from "./views/SettingsView";
import { RunPlannerView } from "./views/RunPlannerView";
import { RunMonitorView } from "./views/RunMonitorView";
import { DiagnosticsView } from "./views/DiagnosticsView";
import { TelemetryView } from "./views/TelemetryView";
import { useSettingsViewModel } from "./viewmodels/useSettingsViewModel";
import { useRunWorkflowViewModel } from "./viewmodels/useRunWorkflowViewModel";
import { useDiagnosticsViewModel } from "./viewmodels/useDiagnosticsViewModel";
import { useTelemetryViewModel } from "./viewmodels/useTelemetryViewModel";
import { StatusBanner } from "./components/StatusBanner";
import { TechnicalErrorPanel } from "./components/TechnicalErrorPanel";

type TabId = "settings" | "planner" | "monitor" | "diagnostics" | "telemetry";

const TAB_LABELS: Array<{ id: TabId; label: string }> = [
  { id: "settings", label: "Settings" },
  { id: "planner", label: "Run Planner" },
  { id: "monitor", label: "Run Monitor" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "telemetry", label: "Telemetry" }
];

export default function App() {
  const [tab, setTab] = useState<TabId>("settings");
  const settingsVm = useSettingsViewModel();
  const runVm = useRunWorkflowViewModel(settingsVm.settings);
  const diagnosticsVm = useDiagnosticsViewModel(settingsVm.settings);
  const telemetryVm = useTelemetryViewModel(settingsVm.settings);
  const configuredBoxIds = useMemo(
    () => settingsVm.settings.boxes.map((item) => item.boxId),
    [settingsVm.settings.boxes]
  );

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">SEVA</p>
          <h1>Web UI (Vite + React)</h1>
          <p>Two-track runtime: this web client coexists with the Tkinter desktop application.</p>
        </div>
      </header>

      <nav className="tabs">
        {TAB_LABELS.map((item) => (
          <button
            key={item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <main className="content">
        <StatusBanner text={settingsVm.savedAt ? `Settings saved at ${settingsVm.savedAt}` : undefined} />
        <StatusBanner text={runVm.info || diagnosticsVm.info || telemetryVm.info} />
        <TechnicalErrorPanel error={settingsVm.error || runVm.error || diagnosticsVm.error || telemetryVm.error} />

        {tab === "settings" ? (
          <SettingsView
            settings={settingsVm.settings}
            savedAt={settingsVm.savedAt}
            loading={settingsVm.loading}
            onUpdateBox={(boxId, field, value) =>
              settingsVm.updateBox(boxId, {
                [field]: value
              })
            }
            onUpdateField={settingsVm.updateField}
            onSave={settingsVm.save}
            onExport={settingsVm.exportJson}
            onImport={settingsVm.importJson}
            onReset={settingsVm.resetDefaults}
          />
        ) : null}

        {tab === "planner" ? (
          <RunPlannerView
            entries={runVm.entries}
            boxes={configuredBoxIds}
            busy={runVm.isBusy}
            validationSummary={runVm.validationSummary}
            onAddEntry={runVm.addEntry}
            onRemoveEntry={runVm.removeEntry}
            onUpdateField={runVm.updateEntryField}
            onToggleMode={runVm.toggleMode}
            onUpdateModeJson={runVm.updateModeJson}
            onValidateEntry={runVm.validateEntryModes}
            onStart={() => runVm.start(settingsVm.settings.experimentName, settingsVm.settings.subdir)}
          />
        ) : null}

        {tab === "monitor" ? (
          <RunMonitorView
            history={runVm.groupHistory}
            activeGroup={runVm.activeGroup}
            activeSnapshot={runVm.activeSnapshot}
            selectedRunIds={runVm.selectedRunIds}
            autoPolling={runVm.autoPolling}
            busy={runVm.isBusy}
            onSelectGroup={runVm.setActiveGroup}
            onSetSelectedRunIds={runVm.setSelectedRunIds}
            onPollNow={runVm.pollNow}
            onToggleAutoPolling={runVm.setAutoPolling}
            onCancelGroup={runVm.cancelActiveGroup}
            onCancelSelected={runVm.cancelSelectedRuns}
            onDownloadGroup={runVm.downloadActiveGroup}
          />
        ) : null}

        {tab === "diagnostics" ? (
          <DiagnosticsView
            boxes={configuredBoxIds}
            busy={diagnosticsVm.isBusy}
            connections={diagnosticsVm.connections}
            discoveryResults={diagnosticsVm.discoveryResults}
            rescanResults={diagnosticsVm.rescanResults}
            deviceStatus={diagnosticsVm.deviceStatus}
            nasResponse={diagnosticsVm.nasResponse}
            onRunConnectionTests={diagnosticsVm.runConnectionTests}
            onRunDiscovery={diagnosticsVm.runDiscovery}
            onRunRescan={diagnosticsVm.runRescan}
            onRefreshStatus={diagnosticsVm.refreshStatus}
            onFlashFirmware={diagnosticsVm.flashFirmware}
            onRunNasSetup={diagnosticsVm.runNasSetup}
            onRunNasHealth={diagnosticsVm.runNasHealth}
            onRunNasUpload={diagnosticsVm.runNasUpload}
          />
        ) : null}

        {tab === "telemetry" ? (
          <TelemetryView
            boxes={configuredBoxIds}
            selectedBoxId={telemetryVm.boxId}
            samples={telemetryVm.samples}
            streaming={telemetryVm.isStreaming}
            busy={false}
            onSelectBox={telemetryVm.setBoxId}
            onRefresh={telemetryVm.refresh}
            onStreamingChange={telemetryVm.setStreaming}
          />
        ) : null}
      </main>
    </div>
  );
}
