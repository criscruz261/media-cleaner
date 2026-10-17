import { ScannerResetContext } from "./ScannerResetContext";
import { useState } from "react";
import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GroupFilterContext, type GroupFilter } from "./GroupFilters";
import { ScanProgress } from "./ScanProgress";

it("shows deletion counts for the active filter independently of the overall scan count", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("selection-summary")
          ? url.includes("EXACT_DUPLICATE")
            ? { selected_files: 3, total_files: 6 }
            : { selected_files: 4, total_files: 9 }
          : { status: "completed", processed: 7706, discovered: 7706 },
    })),
  );
  function Harness() {
    const [filter, setFilter] = useState<GroupFilter>("");
    return (
      <GroupFilterContext.Provider value={[filter, setFilter]}>
        <button onClick={() => setFilter("EXACT_DUPLICATE")}>Exact only</button>
        <ScanProgress scanId="scan" />
      </GroupFilterContext.Provider>
    );
  }
  try {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Harness />
      </QueryClientProvider>,
    );
    await screen.findByText("4 / 9 files selected for deletion");
    expect(
      screen.getByText("Scan completed · 7706 / 7706 files processed"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Exact only" }));
    await screen.findByText("3 / 6 files selected for deletion");
    expect(
      screen.getByText("Exact duplicates only · all pages"),
    ).toBeInTheDocument();
  } finally {
    vi.unstubAllGlobals();
  }
});

it("stops an active scan using the safe stop action and keeps saved results visible", async () => {
  const reset = vi.fn();
  let status = "running";
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith("/stop")) status = "cancelled";
    return {
      ok: true,
      json: async () =>
        url.includes("selection-summary")
          ? { selected_files: 1, total_files: 2 }
          : {
              status,
              stage:
                status === "cancelled"
                  ? "Scan stopped; completed results and checkpoints saved"
                  : "metadata_and_hashing",
              processed: 2,
              discovered: 3,
            },
    };
  });
  vi.stubGlobal("fetch", fetch);
  try {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ScannerResetContext.Provider value={reset}>
          <ScanProgress scanId="scan" />
        </ScannerResetContext.Provider>
      </QueryClientProvider>,
    );
    await screen.findByRole("button", { name: "Pause & save checkpoint" });
    fireEvent.click(screen.getByRole("button", { name: "Stop scan" }));
    await screen.findByText("Scan cancelled · 2 / 3 files processed");
    expect(reset).toHaveBeenCalledOnce();
    expect(
      fetch.mock.calls.some(([url]) => url.endsWith("/scans/scan/stop")),
    ).toBe(true);
    expect(
      screen.getByText(/Scan stopped. Saved results remain available/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Resume from checkpoint" }),
    ).not.toBeInTheDocument();
  } finally {
    vi.unstubAllGlobals();
  }
});
