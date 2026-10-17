import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BatchCleanup } from "./BatchCleanup";

it("previews selections across the scan without executing cleanup", async () => {
  const fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({ id: "combined-plan" }),
  }));
  vi.stubGlobal("fetch", fetch);
  try {
    const onPlan = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <BatchCleanup scanId="scan" onPlan={onPlan} />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Batch cleanup destination"), {
      target: { value: "quarantine" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Delete selected across groups" }),
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
    });
  } finally {
    vi.unstubAllGlobals();
  }
});
