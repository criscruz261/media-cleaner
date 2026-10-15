import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LiveMatches } from "./LiveMatches";

it.each(["running", "completed"])(
  "supports group selection and deletion while %s",
  async (status) => {
    const group = {
      id: "group",
      member_count: 2,
      classification: "EXACT_DUPLICATE",
      evidence: {},
      recoverable: 5,
    };
    let keep = true;
    const file = (id: string) => ({
      id,
      name: id + ".MOV",
      path: "/" + id,
      media_type: "video",
      size: 5,
      status: "ready",
      keep: id === "one" || keep,
      metadata: {},
      warnings: [],
    });
    const fetch = vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith("/review")) keep = false;
      return {
        ok: true,
        json: async () =>
          url.includes("/matches")
            ? { items: [group], total: 1, exact_groups: 1, similar_groups: 0 }
            : url.endsWith("/settings")
              ? { cleanup_destination: "trash" }
              : url.endsWith("/cleanup/plan")
                ? { id: "plan" }
                : { ...group, files: [file("one"), file("two")] },
      };
    });
    vi.stubGlobal("fetch", fetch);
    const onPlan = vi.fn();
    try {
      render(
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <LiveMatches
            scanId="scan"
            status={status}
            navigate={vi.fn()}
            onPlan={onPlan}
          />
        </QueryClientProvider>,
      );
      await waitFor(() =>
        expect(screen.getAllByRole("checkbox")).toHaveLength(2),
      );
      expect(screen.getAllByRole("checkbox")[0]).not.toBeChecked();
      expect(
        screen.getByRole("button", { name: /Delete selected · 0/ }),
      ).toBeDisabled();
      fireEvent.click(screen.getAllByRole("checkbox")[1]);
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /Delete selected · 1/ }),
        ).toBeEnabled(),
      );
      fireEvent.click(
        screen.getByRole("button", { name: /Delete selected · 1/ }),
      );
      await waitFor(() =>
        expect(onPlan.mock.calls[0]?.[0]).toEqual({ id: "plan" }),
      );
      const reviewCall = fetch.mock.calls.find(([url]) =>
        url.endsWith("/review"),
      )!;
      expect(JSON.parse(reviewCall[1]!.body as string)).toEqual({
        changes: { two: false },
      });
      const call = fetch.mock.calls.find(([url]) =>
        url.endsWith("/cleanup/plan"),
      )!;
      expect(JSON.parse(call[1]!.body as string)).toMatchObject({
        group_id: "group",
        file_ids: ["two"],
        destination: "trash",
      });
      expect(
        fetch.mock.calls.some(([url]) => url.includes("/cleanup/execute")),
      ).toBe(false);
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
