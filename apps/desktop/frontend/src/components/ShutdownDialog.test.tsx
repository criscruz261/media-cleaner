import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ShutdownControl } from "./ShutdownDialog";

it("requires confirmation before checkpointing and shutting down", async () => {
  const fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({ status: "stopped", checkpoint_saved: true }),
  }));
  vi.stubGlobal("fetch", fetch);
  try {
    const stopped = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ShutdownControl onStopped={stopped} />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Shut down safely" }));
    expect(
      screen.getByRole("button", { name: "Confirm shutdown" }),
    ).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm shutdown" }));
    await waitFor(() => expect(stopped).toHaveBeenCalledOnce());
    const [url, options] = fetch.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toContain("/app/shutdown");
    expect(JSON.parse(options.body as string)).toEqual({ confirmed: true });
  } finally {
    vi.unstubAllGlobals();
  }
});
