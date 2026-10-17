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
