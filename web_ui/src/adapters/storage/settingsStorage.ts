import {
  SETTINGS_STORAGE_KEY,
  WebSettingsDto,
  normalizeSettings
} from "../../domain/settings";

export class SettingsStorageAdapter {
  load(): WebSettingsDto | null {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return normalizeSettings(parsed);
  }

  save(settings: WebSettingsDto): void {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings, null, 2));
  }

  clear(): void {
    window.localStorage.removeItem(SETTINGS_STORAGE_KEY);
  }
}
