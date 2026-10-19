import { usePopupKeyboard } from "./usePopupKeyboard";
import { ScanProgress } from "./ScanProgress";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Pause, RotateCcw } from "lucide-react";
import { api, prefix } from "../services/api";
import type { Group, MediaFile } from "../types/api";
import { ErrorMessage } from "./ui";

export function VideoCompare({
  groupId,
  scanId,
}: {
  groupId: string;
  scanId?: string;
}) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <button
        onClick={(event) => {
          event.currentTarget
            .closest("article")
            ?.querySelectorAll("video")
            .forEach((video) => video.pause());
          setOpen(true);
        }}
      >
        <Play size={15} /> Compare videos together
      </button>
      {open && <Comparison groupId={groupId} scanId={scanId} close={close} />}
    </>
  );
}

function Comparison({
  groupId,
  scanId,
  close,
}: {
  groupId: string;
  scanId?: string;
  close: () => void;
}) {
  const panel = useRef<HTMLElement>(null);
  const trigger = useRef(document.activeElement as HTMLElement | null);
  const [ready, setReady] = useState<Record<string, boolean>>({});
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<unknown>(null);
  const files = useQuery({
    queryKey: ["compare-videos", groupId],
    queryFn: async () => {
      const result: MediaFile[] = [];
      let offset = 0;
      while (true) {
        const page = await api<Group & { files: MediaFile[] }>(
          `/groups/${groupId}?offset=${offset}&limit=50`,
        );
        result.push(
          ...page.files.filter((file) => file.media_type === "video"),
        );
        offset += page.files.length;
        if (offset >= page.member_count || !page.files.length) return result;
      }
    },
  });
  const client = useQueryClient();
  const selection = useMutation({
    mutationFn: ({ id, selected }: { id: string; selected: boolean }) =>
      api(`/groups/${groupId}/review`, { changes: { [id]: !selected } }),
    onSuccess: (_, { id, selected }) => {
      void client.invalidateQueries({ queryKey: ["selection-summary"] });
      client.setQueryData<MediaFile[]>(["compare-videos", groupId], (current) =>
        current?.map((file) =>
          file.id === id ? { ...file, keep: !selected } : file,
        ),
      );
      void client.invalidateQueries({ queryKey: ["group", groupId] });
      void client.invalidateQueries({ queryKey: ["compare-videos", groupId] });
    },
  });
  usePopupKeyboard(true, (event) => {
    if (event.key === "Escape") close();
  });
  const videos = () =>
    Array.from(panel.current?.querySelectorAll("video") ?? []);
  useEffect(() => {
    const element = panel.current;
    element?.querySelector<HTMLButtonElement>("button")?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Tab") {
        const focusable = Array.from(
          element?.querySelectorAll<HTMLElement>(
            "button:not(:disabled), input:not(:disabled), video, a[href]",
          ) ?? [],
        );
        const first = focusable[0],
          last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("keydown", keyboard);
      element?.querySelectorAll("video").forEach((video) => video.pause());
      trigger.current?.focus();
    };
  }, [close]);
  const playable = (files.data ?? []).filter((file) => !failed[file.id]);
  const allReady =
    playable.length > 0 && playable.every((file) => ready[file.id]);
  async function playAll() {
    setError(null);
    const players = videos().filter((video) => !video.error);
    players.forEach((video) => {
      video.pause();
      video.currentTime = 0;
    });
    const results = await Promise.allSettled(
      players.map((video) => video.play()),
    );
    if (results.some((result) => result.status === "rejected")) {
      players.forEach((video) => video.pause());
      setError(
        new Error(
          "A video could not start. Try again or use its individual playback controls.",
        ),
      );
    }
  }
  return (
    <div className="modal-backdrop">
      <section
        ref={panel}
        className="video-compare-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Compare similar videos"
      >
        {scanId && <ScanProgress scanId={scanId} />}
        <div className="section-heading">
          <h2>Compare similar videos</h2>
          <button onClick={close}>Close comparison</button>
        </div>
        <p>
          Play all starts every video from the beginning. Videos start muted;
          unmute individual players to compare audio. Buffering can affect
          timing.
        </p>
        <div className="actions">
          <button
            className="primary"
            disabled={!allReady}
            onClick={() => void playAll()}
          >
            <Play size={15} /> Play all from start
          </button>
          <button onClick={() => videos().forEach((video) => video.pause())}>
            <Pause size={15} /> Pause all
          </button>
          <button
            onClick={() =>
              videos().forEach((video) => {
                video.pause();
                video.currentTime = 0;
              })
            }
          >
            <RotateCcw size={15} /> Reset all
          </button>
        </div>
        {files.isPending && <p role="status">Loading group videos…</p>}
        {files.data && !allReady && playable.length > 0 && (
          <p role="status">Preparing videos for playback…</p>
        )}
        <p className="hint">
          Select unwanted videos for deletion. Selections are saved to the
          group; close this window to review and confirm cleanup. Unselected
          videos are kept.
        </p>
        <ErrorMessage error={files.error || selection.error || error} />
        <div className="media-grid">
          {files.data?.map((file) => (
            <div
              className={`media-card ${!file.keep ? "selected-for-deletion" : ""}`}
              key={file.id}
            >
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  aria-label={`Select ${file.name} for deletion`}
                  checked={!file.keep}
                  disabled={
                    selection.isPending ||
                    !!file.protected_reason ||
                    file.status !== "ready"
                  }
                  onChange={(event) =>
                    selection.mutate({
                      id: file.id,
                      selected: event.target.checked,
                    })
                  }
                />
                Select for deletion
              </label>
              {file.protected_reason && (
                <p className="protected">{file.protected_reason}</p>
              )}
              <strong className="filename">{file.name}</strong>
              <video
                controls
                muted
                playsInline
                preload="auto"
                poster={`${prefix}/files/${file.id}/thumbnail`}
                src={`${prefix}/files/${file.id}/preview`}
                aria-label={file.name}
                onCanPlay={() =>
                  setReady((current) => ({ ...current, [file.id]: true }))
                }
                onError={() =>
                  setFailed((current) => ({ ...current, [file.id]: true }))
                }
              />
              {failed[file.id] && <p>Preview unavailable for this video.</p>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
