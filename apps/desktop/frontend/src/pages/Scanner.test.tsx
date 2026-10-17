import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Scanner } from "./Scanner";
describe("scanner", () => {
  it("submits multiple real roots and exclusions and enables similar-photo scanning", async () => {
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
      screen.getByRole("option", { name: /Similar photos, videos/ }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start scan" }));
    await waitFor(() => expect(select).toHaveBeenCalledWith("scan-id"));
    const body = JSON.parse(
      (fetch.mock.calls[0] as unknown as [string, RequestInit])[1]
        .body as string,
    );
    expect(body.mode).toBe("similar");
    expect(body.sensitivity).toBe("balanced");
    expect(body.roots).toEqual(["/photos", "/Volumes/External"]);
    expect(body.excluded_extensions).toEqual([".lrv", ".insv"]);
    vi.unstubAllGlobals();
  });
});

it("toggles processing thumbnails in Current scan and remembers the preference", async () => {
  localStorage.removeItem("media-cleaner.scan-thumbnails");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("/matches")
          ? { items: [], total: 0, exact_groups: 0, similar_groups: 0 }
          : {
              id: "scan",
              status: "running",
              stage: "metadata_and_hashing",
              discovered: 2,
              processed: 0,
              bytes_processed: 0,
              total_bytes: 100,
              cache_hits: 0,
              errors: 0,
              options: { roots: ["/photos"] },
              activity: [
                {
                  file_id: "file",
                  path: "/photos/current.jpg",
                  phase: "comparing image",
                  size: 100,
                  bytes_done: 0,
                },
              ],
            },
    })),
  );
  try {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Scanner scanId="scan" selectScan={vi.fn()} navigate={vi.fn()} />
      </QueryClientProvider>,
    );
    const image = await screen.findByRole("img", {
      name: "Processing current.jpg",
    });
    expect(image).toHaveAttribute("src", "/api/v1/files/file/thumbnail");
    const toggle = screen.getByRole("switch", {
      name: "Show processing thumbnails",
    });
    fireEvent.click(toggle);
    expect(
      screen.queryByRole("img", { name: "Processing current.jpg" }),
    ).not.toBeInTheDocument();
    expect(localStorage.getItem("media-cleaner.scan-thumbnails")).toBe("false");
    fireEvent.click(toggle);
    expect(
      screen.getByRole("img", { name: "Processing current.jpg" }),
    ).toBeInTheDocument();
  } finally {
    vi.unstubAllGlobals();
    localStorage.removeItem("media-cleaner.scan-thumbnails");
  }
});
