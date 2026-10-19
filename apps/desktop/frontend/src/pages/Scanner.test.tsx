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
    expect(
      screen.queryByLabelText("Scan from scratch"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Scan options"));
    expect(
      screen.getByRole("button", { name: "Continue Scan" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Scan options"));
    fireEvent.change(screen.getByLabelText(/Folder paths/), {
      target: { value: "/photos\n/Volumes/External" },
    });
    fireEvent.change(screen.getByLabelText("Exclude extensions"), {
      target: { value: ".lrv, .insv" },
    });
    expect(
      screen.getByRole("option", { name: /Similar photos, videos/ }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Media similarity sensitivity"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText(/Video samples ·/), {
      target: { value: "18" },
    });
    expect(
      screen.getByRole("img", { name: "Loose matching example photo" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("img")).toHaveLength(2);
    for (const [option, example] of [
      ["Strict", "Strict"],
      ["Balanced", "Balanced"],
      ["Loose", "Loose"],
      ["Very loose", "Very loose"],
      ["Extra loose", "Extra loose"],
      ["Maximum", "Maximum"],
    ]) {
      const point = screen.getByRole("button", { name: option });
      fireEvent.click(point);
      expect(point).toHaveAttribute("aria-pressed", "true");
      expect(screen.getAllByRole("img")).toHaveLength(2);
      expect(
        screen.getByRole("img", { name: `${example} matching example photo` }),
      ).toBeInTheDocument();
    }
    fireEvent.click(screen.getAllByRole("button", { name: "Scan" })[0]);
    await waitFor(() => expect(select).toHaveBeenCalledWith("scan-id"));
    const body = JSON.parse(
      (fetch.mock.calls[0] as unknown as [string, RequestInit])[1]
        .body as string,
    );
    expect(body.force_rescan).toBe(false);
    expect(body.mode).toBe("similar");
    expect(body.sensitivity).toBe("maximum");
    expect(body.video_samples).toBe(18);
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

it.each(["paused", "completed"])(
  "continues a %s scan using saved work",
  async (status) => {
    const fetch = vi.fn(async (url: string, init?: RequestInit) => ({
      ok: true,
      json: async () =>
        url.includes("/matches") || url.includes("/warnings")
          ? { items: [], total: 0, exact_groups: 0, similar_groups: 0 }
          : {
              id: "saved-scan",
              status,
              stage: "complete",
              discovered: 2,
              processed: 1,
              bytes_processed: 10,
              total_bytes: 20,
              cache_hits: 0,
              errors: 0,
              options: { roots: ["/photos"] },
              activity: [],
            },
    }));
    vi.stubGlobal("fetch", fetch);
    const view = render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <Scanner scanId="saved-scan" selectScan={vi.fn()} navigate={vi.fn()} />
      </QueryClientProvider>,
    );
    try {
      await screen.findAllByText(status === "paused" ? "Paused" : "Completed");
      const setup = view.container.querySelector("details.scanner-setup")!;
      setup.setAttribute("open", "");
      fireEvent.click(screen.getByLabelText("Scan options"));
      fireEvent.click(screen.getByRole("button", { name: "Continue Scan" }));
      expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(
        false,
      );
      const mainButton = view.container.querySelector<HTMLButtonElement>(
        ".scan-split-button > button",
      )!;
      expect(mainButton).toHaveTextContent("Continue Scan");
      fireEvent.click(screen.getByLabelText("Scan options"));
      fireEvent.click(screen.getByRole("button", { name: "Scan" }));
      expect(mainButton).toHaveTextContent(/^Scan$/);
      expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(
        false,
      );
      fireEvent.click(screen.getByLabelText("Scan options"));
      fireEvent.click(screen.getByRole("button", { name: "Continue Scan" }));
      fireEvent.click(mainButton);
      await waitFor(() =>
        expect(
          fetch.mock.calls.some(
            ([url, init]) =>
              init?.method === "POST" &&
              url ===
                (status === "paused"
                  ? "/api/v1/scans/saved-scan/resume"
                  : "/api/v1/scans"),
          ),
        ).toBe(true),
      );
      if (status === "completed") {
        const [, request] = fetch.mock.calls.find(
          ([url, init]) => url === "/api/v1/scans" && init?.method === "POST",
        )!;
        expect(JSON.parse(request!.body as string).force_rescan).toBe(false);
      }
    } finally {
      view.unmount();
      vi.unstubAllGlobals();
    }
  },
);
