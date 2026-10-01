import { describe, expect, it } from "vitest";

import { cn, formatBytes, formatDateTime, truncate } from "./utils";

describe("cn", () => {
  it("merges class names and resolves Tailwind conflicts in favor of the later one", () => {
    expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4");
  });

  it("drops falsy values", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });
});

describe("formatDateTime", () => {
  it("returns an em dash for null/undefined/empty input", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
    expect(formatDateTime("")).toBe("—");
  });

  it("formats a real ISO timestamp into a non-empty, locale-formatted string", () => {
    const result = formatDateTime("2026-01-15T10:30:00Z");
    expect(result).not.toBe("—");
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("formatBytes", () => {
  it("keeps small values in bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(0)).toBe("0 B");
  });

  it("converts to KB once past 1024 bytes", () => {
    expect(formatBytes(2048)).toBe("2.0 KB");
  });

  it("converts to MB once past 1024 KB", () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("converts to GB once past 1024 MB, and stops there (no TB unit)", () => {
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe("3.0 GB");
    // 1024 GB stays GB — formatBytes has no TB unit, matching the real upload
    // sizes this app ever deals with (documents, never multi-terabyte files).
    expect(formatBytes(1024 * 1024 * 1024 * 1024)).toBe("1024.0 GB");
  });
});

describe("truncate", () => {
  it("leaves short text untouched", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("cuts long text and appends an ellipsis within the max length", () => {
    const result = truncate("hello world", 8);
    expect(result).toBe("hello w…");
    expect(result.length).toBe(8);
  });

  it("treats text exactly at the max length as not needing truncation", () => {
    expect(truncate("12345", 5)).toBe("12345");
  });
});
