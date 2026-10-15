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
