import { useMemo, useState } from "react";
import {
  BoxConnectionDto,
  WebSettingsDto,
  defaultSettings
} from "../domain/settings";
import { asTechnicalError, TechnicalError } from "../domain/errors";
import { SettingsService } from "../services/settingsService";

const service = new SettingsService();

function replaceBox(boxes: BoxConnectionDto[], boxId: string, update: Partial<BoxConnectionDto>) {
  return boxes.map((box) => (box.boxId === boxId ? { ...box, ...update } : box));
}

export interface SettingsViewModel {
  settings: WebSettingsDto;
  savedAt?: string;
  loading: boolean;
  error?: TechnicalError;
  updateBox: (boxId: string, update: Partial<BoxConnectionDto>) => void;
  updateField: <K extends keyof WebSettingsDto>(field: K, value: WebSettingsDto[K]) => void;
  save: () => void;
  exportJson: () => void;
  importJson: (file: File) => Promise<void>;
  resetDefaults: () => void;
}

export function useSettingsViewModel(): SettingsViewModel {
  const initial = useMemo(() => service.load(), []);
  const [settings, setSettings] = useState<WebSettingsDto>(initial);
  const [savedAt, setSavedAt] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<TechnicalError | undefined>(undefined);

  const updateBox = (boxId: string, update: Partial<BoxConnectionDto>): void => {
    setSettings((current) => ({
      ...current,
      boxes: replaceBox(current.boxes, boxId, update)
    }));
  };

  const updateField = <K extends keyof WebSettingsDto>(
    field: K,
    value: WebSettingsDto[K]
  ): void => {
    setSettings((current) => ({
      ...current,
      [field]: value
    }));
  };

  const save = (): void => {
    try {
      const persisted = service.save(settings);
      setSettings(persisted);
      setSavedAt(new Date().toISOString());
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    }
  };

  const exportJson = (): void => {
    try {
      service.export(settings);
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    }
  };

  const importJson = async (file: File): Promise<void> => {
    setLoading(true);
    try {
      const imported = await service.import(file);
      setSettings(imported);
      setSavedAt(new Date().toISOString());
      setError(undefined);
    } catch (err) {
      setError(asTechnicalError(err));
    } finally {
      setLoading(false);
    }
  };

  const resetDefaults = (): void => {
    setSettings(defaultSettings());
    setSavedAt(undefined);
    setError(undefined);
  };

  return {
    settings,
    savedAt,
    loading,
    error,
    updateBox,
    updateField,
    save,
    exportJson,
    importJson,
    resetDefaults
  };
}
