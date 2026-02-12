import {
  WebSettingsDto,
  defaultSettings,
  normalizeSettings
} from "../domain/settings";
import { SettingsStorageAdapter } from "../adapters/storage/settingsStorage";
import { downloadJson, readJsonFile } from "../adapters/browser/fileTransfer";

export class SettingsService {
  private readonly storage = new SettingsStorageAdapter();

  load(): WebSettingsDto {
    const saved = this.storage.load();
    return saved || defaultSettings();
  }

  save(settings: WebSettingsDto): WebSettingsDto {
    const normalized = normalizeSettings(settings);
    this.storage.save(normalized);
    return normalized;
  }

  export(settings: WebSettingsDto): void {
    downloadJson("seva-web-settings.json", settings);
  }

  async import(file: File): Promise<WebSettingsDto> {
    const payload = await readJsonFile<unknown>(file);
    const normalized = normalizeSettings(payload);
    this.storage.save(normalized);
    return normalized;
  }
}
