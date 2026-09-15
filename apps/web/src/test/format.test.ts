import { describe, expect, it } from "vitest";
import { formatDuration, formatTime } from "../lib/format";

describe("time formatting", () => {
  it("formats millisecond positions for the audio editor", () => {
    expect(formatTime(0)).toBe("0:00");
    expect(formatTime(65_432)).toBe("1:05");
    expect(formatDuration(null)).toBe("—");
  });
});
