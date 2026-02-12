import { describe, expect, it } from "vitest";
import {
  defaultSettings,
  normalizeSettings
} from "./settings";

describe("settings normalization", () => {
  it("accepts defaults", () => {
    const normalized = normalizeSettings(defaultSettings());
    expect(normalized.version).toBe(1);
    expect(normalized.boxes).toHaveLength(4);
  });

  it("rejects duplicate box ids", () => {
    const settings = defaultSettings();
    settings.boxes = [
      { boxId: "A", baseUrl: "", apiKey: "" },
      { boxId: "A", baseUrl: "", apiKey: "" }
    ];
    expect(() => normalizeSettings(settings)).toThrowError(/unique/i);
  });
});
