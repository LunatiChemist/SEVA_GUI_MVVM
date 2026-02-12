import { describe, expect, it } from "vitest";
import {
  createEmptyEntry,
  normalizeEntryDraft
} from "./run";

describe("run entry normalization", () => {
  it("normalizes a valid entry", () => {
    const draft = createEmptyEntry("A");
    draft.wellId = "A1";
    draft.slot = "slot01";
    draft.modes = ["CV"];
    draft.modeParamsJson = { CV: "{\"start\":0,\"vertex1\":1,\"vertex2\":-1,\"end\":0,\"scan_rate\":0.1,\"cycles\":1}" };
    const normalized = normalizeEntryDraft(draft);
    expect(normalized.wellId).toBe("A1");
    expect(normalized.modes).toEqual(["CV"]);
  });

  it("rejects invalid slot format", () => {
    const draft = createEmptyEntry("A");
    draft.wellId = "A1";
    draft.slot = "A01";
    draft.modes = ["CV"];
    draft.modeParamsJson = { CV: "{}" };
    expect(() => normalizeEntryDraft(draft)).toThrowError(/slotNN/i);
  });
});
