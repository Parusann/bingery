import { describe, it, expect } from "vitest";
import {
  getSundayOfWeek,
  shiftWeek,
  formatLocalTime,
  formatLocalTzAbbr,
  isToday,
  todayIsoDate,
} from "@/features/schedule/utils";

describe("getSundayOfWeek", () => {
  it("returns the same date when given a Sunday", () => {
    expect(getSundayOfWeek(new Date("2026-05-24T12:00:00Z"))).toBe("2026-05-24");
  });
  it("returns the prior Sunday when given a Wednesday", () => {
    expect(getSundayOfWeek(new Date("2026-05-27T12:00:00Z"))).toBe("2026-05-24");
  });
});

describe("shiftWeek", () => {
  it("adds 7 days for +1", () => {
    expect(shiftWeek("2026-05-24", 1)).toBe("2026-05-31");
  });
  it("subtracts 7 days for -1", () => {
    expect(shiftWeek("2026-05-24", -1)).toBe("2026-05-17");
  });
  it("crosses a month boundary", () => {
    expect(shiftWeek("2026-05-31", 1)).toBe("2026-06-07");
  });
});

describe("isToday", () => {
  it("returns true for today", () => {
    expect(isToday(todayIsoDate())).toBe(true);
  });
  it("returns false for a different day", () => {
    expect(isToday("1999-01-01")).toBe(false);
  });
});

describe("formatLocalTime", () => {
  it("returns h:mm AM/PM in the user's locale", () => {
    const s = formatLocalTime("2026-05-24T22:30:00Z");
    expect(s).toMatch(/\d{1,2}:\d{2}/);
  });
});

describe("formatLocalTzAbbr", () => {
  it("returns a non-empty string", () => {
    expect(formatLocalTzAbbr().length).toBeGreaterThan(0);
  });
});
