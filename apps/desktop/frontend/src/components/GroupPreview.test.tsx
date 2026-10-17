import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GroupPreview } from "./GroupPreview";

it("navigates across group pages, zooms, and saves deletion choices without cleanup", async () => {
  let keep = true;
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/review")) keep = false;
    return {
      ok: true,
      json: async () =>
        url.endsWith("/review")
          ? { saved: true }
          : {
              files: Array.from(
                { length: url.includes("offset=200") ? 1 : 200 },
                (_, i) => {
                  const index = url.includes("offset=200") ? 200 : i;
                  return {
                    id: String(index),
                    name: `photo-${index}.jpg`,
                    media_type: "image",
                    status: "ready",
                    keep,
                    protected_reason: null,
                  };
                },
              ),
            },
    };
  });
  vi.stubGlobal("fetch", fetch);
  try {
    const close = vi.fn();
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <GroupPreview groupId="group" initialId="199" onClose={close} />
      </QueryClientProvider>,
    );
    await screen.findByText("200 / 201");
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(screen.getByText("125%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("photo-200.jpg")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select for deletion" }),
    );
    await waitFor(() => expect(screen.getByRole("checkbox")).toBeChecked());
    const request = fetch.mock.calls.find(([url]) => url.endsWith("/review"));
    expect(JSON.parse(request![1]!.body as string)).toEqual({
      changes: { "200": false },
    });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowLeft" });
    expect(screen.getByText("photo-199.jpg")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Fit to screen" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(close).toHaveBeenCalledOnce();
    expect(fetch.mock.calls.some(([url]) => url.includes("/cleanup/"))).toBe(
      false,
    );
  } finally {
    vi.unstubAllGlobals();
  }
});
