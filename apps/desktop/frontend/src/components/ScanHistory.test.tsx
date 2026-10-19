import { beforeAll, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScanHistory } from "./ScanHistory";
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
});
it.each(["bulk", "row"])(
  "protects favorites and confirms %s deletion before clearing the active scan",
  async (mode) => {
    const fetch = vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/delete")
          ? { deleted_ids: ["b"] }
          : {
              total: 2,
              items: [
                {
                  id: "a",
                  favorite: true,
                  status: "completed",
                  created_at: "2026-10-19",
                  options: { roots: ["/photos"] },
                },
                {
                  id: "b",
                  status: "completed",
                  created_at: "2026-10-19",
                  options: { roots: ["/photos"] },
                },
              ],
            },
    }));
    vi.stubGlobal("fetch", fetch);
    const selectScan = vi.fn();
    const view = render(
      <QueryClientProvider client={new QueryClient()}>
        <ScanHistory scanId="b" selectScan={selectScan} />
      </QueryClientProvider>,
    );
    try {
      expect(await screen.findByLabelText("Select scan a")).toBeDisabled();
      expect(
        screen.getByRole("columnheader", { name: "Scan ID" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Delete scan a" }),
      ).toBeDisabled();
      if (mode === "row") {
        fireEvent.click(screen.getByRole("button", { name: "Delete scan b" }));
      } else {
        fireEvent.click(
          screen.getByLabelText("Select all eligible scans on this page"),
        );
        expect(screen.getByLabelText("Select scan b")).toBeChecked();
        expect(screen.getByLabelText("Select scan a")).not.toBeChecked();
        fireEvent.click(screen.getByRole("button", { name: "Delete (1)" }));
      }
      expect(fetch.mock.calls.some(([url]) => url.endsWith("/delete"))).toBe(
        false,
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Confirm delete history" }),
      );
      await waitFor(() => expect(selectScan).toHaveBeenCalledWith(""));
    } finally {
      view.unmount();
      vi.unstubAllGlobals();
    }
  },
);

it("shows deletion failures in a popup that disappears after three seconds", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: !url.endsWith("/delete"),
      json: async () =>
        url.endsWith("/delete")
          ? { error: { message: "Scan is protected" } }
          : {
              total: 1,
              items: [
                {
                  id: "b",
                  status: "completed",
                  created_at: "2026-10-19",
                  options: { roots: ["/photos"] },
                },
              ],
            },
    })),
  );
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <ScanHistory scanId="b" selectScan={vi.fn()} />
    </QueryClientProvider>,
  );
  try {
    fireEvent.click(
      await screen.findByRole("button", { name: "Delete scan b" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm delete history" }),
    );
    expect(
      await screen.findByText(
        "Could not delete scan history: Scan is protected",
      ),
    ).toHaveAttribute("role", "alert");
    await waitFor(
      () =>
        expect(
          screen.queryByText(
            "Could not delete scan history: Scan is protected",
          ),
        ).not.toBeInTheDocument(),
      { timeout: 4000 },
    );
    expect(
      screen.getByRole("button", { name: "Confirm delete history" }),
    ).toBeEnabled();
  } finally {
    view.unmount();
    vi.unstubAllGlobals();
  }
});

it("removes deleted rows immediately while the history refresh is pending", async () => {
  let deleted = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/delete")) {
        deleted = true;
        return { ok: true, json: async () => ({ deleted_ids: ["b"] }) };
      }
      if (deleted) return new Promise(() => {});
      return {
        ok: true,
        json: async () => ({
          total: 1,
          items: [
            {
              id: "b",
              status: "completed",
              created_at: "2026-10-19",
              options: { roots: ["/photos"] },
            },
          ],
        }),
      };
    }),
  );
  const client = new QueryClient();
  const view = render(
    <QueryClientProvider client={client}>
      <ScanHistory scanId="" selectScan={vi.fn()} />
    </QueryClientProvider>,
  );
  try {
    fireEvent.click(
      await screen.findByRole("button", { name: "Delete scan b" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Delete scan history?" }),
    ).toBeInTheDocument();
    expect(deleted).toBe(false);
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm delete history" }),
    );
    await waitFor(() =>
      expect(screen.queryByLabelText("Select scan b")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("No scan history.")).toBeInTheDocument();
  } finally {
    view.unmount();
    client.clear();
    vi.unstubAllGlobals();
  }
});
