import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Dashboard } from "./Dashboard";

it("clears and restores the dashboard view without deleting server records", async () => {
  localStorage.removeItem("media-cleaner.dashboard-cleared");
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("/dashboard")
        ? {
            scan_id: "scan",
            files: 10,
            bytes: 100,
            groups: 1,
            similar_groups: 0,
            recoverable: 50,
          }
        : url.includes("/scans?")
          ? {
              items: [
                {
                  id: "scan",
                  status: "completed",
                  options: { roots: ["/photos"] },
                  discovered: 10,
                  cache_hits: 0,
                  created_at: "2026-10-17T12:00:00Z",
                },
              ],
              total: 1,
            }
          : {
              items: [
                {
                  id: "cleanup",
                  status: "completed",
                  destination: "trash",
                  items: [],
                  created_at: "2026-10-17T12:00:00Z",
                },
              ],
              total: 1,
            },
  }));
  vi.stubGlobal("fetch", fetch);
  try {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Dashboard navigate={vi.fn()} selectScan={vi.fn()} />
      </QueryClientProvider>,
    );
    await screen.findByText("/photos");
    fireEvent.click(
      screen.getByRole("button", { name: "Clear dashboard view" }),
    );
    expect(screen.queryByText("/photos")).not.toBeInTheDocument();
    expect(screen.getByText(/Latest scan hidden/)).toBeInTheDocument();
    expect(
      JSON.parse(localStorage.getItem("media-cleaner.dashboard-cleared")!),
    ).toEqual({ scans: ["scan"], cleanup: ["cleanup"] });
    fireEvent.click(
      screen.getByRole("button", { name: "Restore cleared entries" }),
    );
    expect(screen.getByText("/photos")).toBeInTheDocument();
    expect(fetch.mock.calls.every(([url]) => !url.includes("/delete"))).toBe(
      true,
    );
  } finally {
    vi.unstubAllGlobals();
    localStorage.removeItem("media-cleaner.dashboard-cleared");
  }
});
