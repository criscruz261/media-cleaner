import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BatchCleanup } from "./BatchCleanup";

it.each(["", "EXACT_DUPLICATE", "SIMILAR_CONTENT"] as const)(
  "previews selections in scope %s without executing cleanup",
  async (classification) => {
    const fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ id: "combined-plan" }),
    }));
    vi.stubGlobal("fetch", fetch);
    try {
      const onPlan = vi.fn();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <BatchCleanup
            scanId="scan"
            onPlan={onPlan}
            classification={classification}
          />
        </QueryClientProvider>,
      );
      fireEvent.change(screen.getByLabelText("Batch cleanup destination"), {
        target: { value: "quarantine" },
      });
      fireEvent.click(
        screen.getByRole("button", {
          name:
            classification === "EXACT_DUPLICATE"
              ? "Review exact duplicate groups"
              : classification === "SIMILAR_CONTENT"
                ? "Review similar media groups"
                : "Review selected groups",
        }),
      );
      await waitFor(() =>
        expect(onPlan).toHaveBeenCalledWith({ id: "combined-plan" }),
      );
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, options] = fetch.mock.calls[0] as unknown as [
        string,
        RequestInit,
      ];
      expect(url).toContain("/cleanup/plan-selected");
      expect(JSON.parse(options.body as string)).toEqual({
        scan_id: "scan",
        destination: "quarantine",
        ...(classification ? { classification } : {}),
      });
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
