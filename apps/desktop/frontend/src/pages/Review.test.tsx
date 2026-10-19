import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Review } from "./Review";

it("requires choosing a scan before loading results and returns to history", async () => {
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.includes("/scans?")
        ? {
            total: 1,
            items: [
              {
                id: "saved",
                status: "completed",
                created_at: "2026-10-19",
                options: { roots: ["/photos"] },
              },
            ],
          }
        : { total: 0, items: [] },
  }));
  vi.stubGlobal("fetch", fetch);
  const selectScan = vi.fn();
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <Review
        scanId="saved"
        selectScan={selectScan}
        onPlan={vi.fn()}
        navigate={vi.fn()}
      />
    </QueryClientProvider>,
  );
  try {
    expect(
      screen.getByRole("region", { name: "Scan history" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Review scan" }),
    ).toBeInTheDocument();
    expect(fetch.mock.calls.some(([url]) => url.includes("/groups?"))).toBe(
      false,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review scan" }));
    expect(selectScan).toHaveBeenCalledWith("saved");
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(([url]) => url.includes("/groups?scan_id=saved")),
      ).toBe(true),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Back to scan history/ }),
    );
    expect(
      screen.getByRole("region", { name: "Scan history" }),
    ).toBeInTheDocument();
  } finally {
    view.unmount();
    vi.unstubAllGlobals();
  }
});
