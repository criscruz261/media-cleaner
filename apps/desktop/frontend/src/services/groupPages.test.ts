import { expect, it, vi } from "vitest";
import type { Group, Page } from "../types/api";
import { groupPage } from "./groupPages";

it.each([100, 749])(
  "loads %s groups using bounded requests without skipping groups",
  async (size) => {
    const requests: URL[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => {
        const url = new URL(path, "http://localhost");
        requests.push(url);
        const offset = Number(url.searchParams.get("offset"));
        const limit = Number(url.searchParams.get("limit"));
        return {
          ok: true,
          json: async () => ({
            total: 749,
            items: Array.from(
              { length: Math.min(limit, 749 - offset) },
              (_, i) => ({ id: String(offset + i) }),
            ),
          }),
        };
      }),
    );
    try {
      const result = await groupPage<Page<Group>>(
        "/groups?scan_id=scan&classification=EXACT_DUPLICATE",
        0,
        size,
      );
      expect(result.items.map((group) => group.id)).toEqual(
        Array.from({ length: size }, (_, i) => String(i)),
      );
      expect(result.total).toBe(749);
      expect(requests).toHaveLength(Math.ceil(size / 50));
      expect(
        requests.every((url) => Number(url.searchParams.get("limit")) <= 50),
      ).toBe(true);
      expect(
        requests.every(
          (url) => url.searchParams.get("classification") === "EXACT_DUPLICATE",
        ),
      ).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
