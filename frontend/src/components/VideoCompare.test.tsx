import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VideoCompare } from "./VideoCompare";
it("loads all group pages and controls every video together", async () => {
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => ({
      member_count: 2,
      files: [
        {
          id: url.includes("offset=0") ? "one" : "two",
          media_type: "video",
          name: url.includes("offset=0") ? "one.mp4" : "two.mp4",
        },
      ],
    }),
  }));
  vi.stubGlobal("fetch", fetch);
  const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const pause = vi
    .spyOn(HTMLMediaElement.prototype, "pause")
    .mockImplementation(() => {});
  try {
    const { container } = render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <VideoCompare groupId="group" />
      </QueryClientProvider>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Compare videos together" }),
    );
    await waitFor(() =>
      expect(container.querySelectorAll("video")).toHaveLength(2),
    );
    expect(fetch).toHaveBeenCalledTimes(2);
    const players = container.querySelectorAll("video");
    const start = screen.getByRole("button", { name: "Play all from start" });
    expect(start).toBeDisabled();
    players.forEach((player) => fireEvent.canPlay(player));
    expect(start).toBeEnabled();
    players.forEach((player) => {
      player.currentTime = 7;
    });
    fireEvent.click(start);
    await waitFor(() => expect(play).toHaveBeenCalledTimes(2));
    players.forEach((player) => expect(player.currentTime).toBe(0));
    pause.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Pause all" }));
    expect(pause).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "Reset all" }));
    players.forEach((player) => expect(player.currentTime).toBe(0));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  } finally {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  }
});

it("saves video selections to the group and protects protected files", async () => {
  let selected = false;
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/review"))
      selected = !JSON.parse(options!.body as string).changes.one;
    return {
      ok: true,
      json: async () => ({
        member_count: 2,
        files: [
          {
            id: "one",
            name: "one.mp4",
            media_type: "video",
            keep: !selected,
            status: "ready",
            protected_reason: null,
          },
          {
            id: "two",
            name: "two.mp4",
            media_type: "video",
            keep: true,
            status: "ready",
            protected_reason: "Protected directory",
          },
        ],
      }),
    };
  });
  vi.stubGlobal("fetch", fetch);
  const pause = vi
    .spyOn(HTMLMediaElement.prototype, "pause")
    .mockImplementation(() => {});
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(["group", "group", 0], { files: [] });
  try {
    render(
      <QueryClientProvider client={client}>
        <VideoCompare groupId="group" />
      </QueryClientProvider>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Compare videos together" }),
    );
    const checkbox = await screen.findByRole("checkbox", {
      name: "Select one.mp4 for deletion",
    });
    expect(checkbox).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Select two.mp4 for deletion" }),
    ).toBeDisabled();
    fireEvent.click(checkbox);
    await waitFor(() => expect(checkbox).toBeChecked());
    expect(
      JSON.parse(
        fetch.mock.calls.find(([url]) => url.endsWith("/review"))![1]!
          .body as string,
      ),
    ).toEqual({ changes: { one: false } });
    expect(client.getQueryState(["group", "group", 0])!.isInvalidated).toBe(
      true,
    );
    fireEvent.click(checkbox);
    await waitFor(() => expect(checkbox).not.toBeChecked());
    expect(
      fetch.mock.calls.some(([url]) => url.includes("/cleanup/execute")),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Close comparison" }));
  } finally {
    pause.mockRestore();
    vi.unstubAllGlobals();
  }
});
