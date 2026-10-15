import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Scanner } from "./Scanner";
describe("scanner", () => {
  it("submits multiple real roots and exclusions and exposes only Phase 1 modes", async () => {
    const fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ id: "scan-id", status: "completed" }),
    }));
    vi.stubGlobal("fetch", fetch);
    const select = vi.fn();
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <Scanner scanId="" selectScan={select} navigate={vi.fn()} />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText(/Folder paths/), {
      target: { value: "/photos\n/Volumes/External" },
    });
    fireEvent.change(screen.getByLabelText("Exclude extensions"), {
      target: { value: ".lrv, .insv" },
    });
    expect(
      screen.queryByRole("option", { name: /similarity/ }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start scan" }));
    await waitFor(() => expect(select).toHaveBeenCalledWith("scan-id"));
    const body = JSON.parse(
      (fetch.mock.calls[0] as unknown as [string, RequestInit])[1]
        .body as string,
    );
    expect(body.roots).toEqual(["/photos", "/Volumes/External"]);
    expect(body.excluded_extensions).toEqual([".lrv", ".insv"]);
    vi.unstubAllGlobals();
  });
});
