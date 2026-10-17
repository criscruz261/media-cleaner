import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CleanupDialog } from "./CleanupDialog";
import type { Cleanup } from "../types/api";

it("confirms and executes in a pop-up, reports failures, and keeps the results page", async () => {
  const plan = {
    id: "plan",
    token: "token",
    status: "planned",
    destination: "trash",
    total_bytes: 10,
    expires_at: "2026-10-17T12:00:00Z",
    items: [{ file_id: "file", source: "/a.jpg", keeper: null, size: 10 }],
  } as Cleanup;
  const fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      ...plan,
      status: "partial",
      items: [
        { ...plan.items[0], status: "failed", error: "Trash unavailable" },
      ],
    }),
  }));
  vi.stubGlobal("fetch", fetch);
  try {
    const close = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <h1>Matches found so far</h1>
        <CleanupDialog plan={plan} onClose={close} />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm cleanup" }),
    ).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm cleanup" }));
    await screen.findByText("Trash unavailable", { exact: false });
    expect(
      screen.getByRole("heading", { name: "Matches found so far" }),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() => expect(close).toHaveBeenCalledOnce());
  } finally {
    vi.unstubAllGlobals();
  }
});

it("shows live progress after confirmation until cleanup completes", async () => {
  const plan = {
    id: "progress-plan",
    token: "token",
    status: "planned",
    destination: "trash",
    total_bytes: 20,
    expires_at: "2026-10-17T12:00:00Z",
    items: [
      { file_id: "one", source: "/one.jpg", keeper: null, size: 10 },
      { file_id: "two", source: "/two.jpg", keeper: null, size: 10 },
    ],
  } as Cleanup;
  let finish!: (value: unknown) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/execute"))
        return new Promise((resolve) => {
          finish = resolve;
        });
      return {
        ok: true,
        json: async () => ({
          status: "executing",
          total: 2,
          processed: 1,
          moved: 1,
          failed: 0,
          moved_bytes: 10,
          total_bytes: 20,
          current_file: "/two.jpg",
          current_action: "moving",
        }),
      };
    }),
  );
  try {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <CleanupDialog plan={plan} onClose={vi.fn()} />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm cleanup" }));
    await screen.findByText("1 / 2 files processed");
    expect(
      screen.getByRole("progressbar", { name: "Deletion progress" }),
    ).toHaveAttribute("value", "1");
    expect(screen.getByText("Moving: /two.jpg")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm cleanup" }),
    ).not.toBeInTheDocument();
    finish({ ok: true, json: async () => ({ ...plan, status: "completed" }) });
    await screen.findByText("Cleanup completed");
  } finally {
    vi.unstubAllGlobals();
  }
});
