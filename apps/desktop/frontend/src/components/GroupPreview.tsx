import { usePopupKeyboard } from "./usePopupKeyboard";
import { ScanProgress } from "./ScanProgress";
import { createContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, prefix } from "../services/api";
import type { Group, MediaFile } from "../types/api";
import { ErrorMessage } from "./ui";

export const PreviewContext = createContext<
  ((groupId: string, initialId: string, scanId: string) => void) | null
>(null);

export function GroupPreview({
  groupId,
  initialId,
  onClose,
  scanId,
}: {
  groupId: string;
  initialId: string;
  onClose: () => void;
  scanId?: string;
}) {
  const [currentId, setCurrentId] = useState(initialId);
  const [zoom, setZoom] = useState(1);
  const [failed, setFailed] = useState(false);
  const [pendingChoice, setPendingChoice] = useState<{
    id: string;
    keep: boolean;
  } | null>(null);
  const root = useRef<HTMLElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const client = useQueryClient();
  const detail = useQuery({
    queryKey: ["group", groupId, "preview"],
    queryFn: async () => {
      const files: MediaFile[] = [];
      for (let offset = 0; ; offset += 200) {
        const page = await api<Group & { files: MediaFile[] }>(
          `/groups/${groupId}?offset=${offset}&limit=200`,
        );
        files.push(...page.files);
        if (page.files.length < 200) return files;
      }
    },
  });
  const files = detail.data ?? [];
  const index = files.findIndex((file) => file.id === currentId);
  const file = files[index];
  const review = useMutation({
    mutationFn: ({ id, keep }: { id: string; keep: boolean }) =>
      api(`/groups/${groupId}/review`, { changes: { [id]: keep } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["group", groupId] }),
    onSettled: () => setPendingChoice(null),
  });
  const move = (direction: number) => {
    const next = files[index + direction];
    if (next) {
      setCurrentId(next.id);
      root.current?.focus();
    }
  };
  useEffect(() => {
    setZoom(1);
    setFailed(false);
    viewport.current?.scrollTo?.(0, 0);
  }, [currentId]);
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    root.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      prior?.focus();
    };
  }, []);
  usePopupKeyboard(true, (event) => {
    if (event.key === "Escape") onClose();
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      event.stopImmediatePropagation();
      move(event.key === "ArrowLeft" ? -1 : 1);
    }
  });
  return createPortal(
    <div className="modal-backdrop group-preview-backdrop" onClick={onClose}>
      <section
        ref={root}
        className="group-preview"
        role="dialog"
        aria-modal="true"
        aria-label="Group preview"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "+" || event.key === "=")
            setZoom((value) => Math.min(5, value + 0.25));
          if (event.key === "-") setZoom((value) => Math.max(1, value - 0.25));
          if (event.key === "Tab") {
            const controls = [
              ...root.current!.querySelectorAll<HTMLElement>(
                "button:not(:disabled), input:not(:disabled), video[controls]",
              ),
            ];
            const first = controls[0],
              last = controls[controls.length - 1];
            if (
              event.shiftKey &&
              (document.activeElement === first ||
                document.activeElement === root.current)
            ) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        {scanId && <ScanProgress scanId={scanId} />}
        <div className="group-preview-toolbar">
          <button onClick={onClose}>Close preview</button>
          <button disabled={index <= 0} onClick={() => move(-1)}>
            Previous
          </button>
          <span aria-live="polite">
            {index < 0 ? 0 : index + 1} / {files.length}
          </span>
          <button
            disabled={index < 0 || index >= files.length - 1}
            onClick={() => move(1)}
          >
            Next
          </button>
          <button
            aria-label="Zoom out"
            disabled={zoom <= 1}
            onClick={() => setZoom((value) => Math.max(1, value - 0.25))}
          >
            −
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button
            aria-label="Zoom in"
            disabled={zoom >= 5}
            onClick={() => setZoom((value) => Math.min(5, value + 0.25))}
          >
            +
          </button>
          <button onClick={() => setZoom(1)}>Fit to screen</button>
          {file && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={
                  !(pendingChoice?.id === file.id
                    ? pendingChoice.keep
                    : file.keep)
                }
                disabled={
                  review.isPending ||
                  !!file.protected_reason ||
                  file.status !== "ready"
                }
                onChange={() => {
                  const choice = { id: file.id, keep: !file.keep };
                  setPendingChoice(choice);
                  review.mutate(choice);
                }}
              />
              Select for deletion
            </label>
          )}
        </div>
        <strong className="group-preview-name">
          {file?.name ??
            (detail.isPending
              ? "Loading group…"
              : "File no longer in this group")}
        </strong>
        {file?.protected_reason && <p>{file.protected_reason}</p>}
        <div
          className="group-preview-media"
          ref={viewport}
          onPointerDown={(event) => {
            if (zoom > 1 && file?.media_type !== "video") {
              event.currentTarget.setPointerCapture(event.pointerId);
              event.currentTarget.dataset.x = String(event.clientX);
              event.currentTarget.dataset.y = String(event.clientY);
            }
          }}
          onPointerMove={(event) => {
            const target = event.currentTarget;
            if (!target.hasPointerCapture(event.pointerId)) return;
            target.scrollLeft -= event.clientX - Number(target.dataset.x);
            target.scrollTop -= event.clientY - Number(target.dataset.y);
            target.dataset.x = String(event.clientX);
            target.dataset.y = String(event.clientY);
          }}
          onPointerUp={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId))
              event.currentTarget.releasePointerCapture(event.pointerId);
          }}
        >
          {file && !failed ? (
            <div
              className="group-preview-canvas"
              style={{ width: `${zoom * 100}%`, height: `${zoom * 100}%` }}
            >
              {file.media_type === "video" ? (
                <video
                  key={file.id}
                  controls
                  playsInline
                  preload="metadata"
                  src={`${prefix}/files/${file.id}/preview`}
                  onError={() => setFailed(true)}
                />
              ) : (
                <img
                  key={file.id}
                  draggable={false}
                  src={`${prefix}/files/${file.id}/preview`}
                  alt={file.name}
                  onError={() => setFailed(true)}
                />
              )}
            </div>
          ) : failed ? (
            <p>
              Preview unavailable for this format. You can still navigate and
              change the selection.
            </p>
          ) : null}
        </div>
        <ErrorMessage error={detail.error || review.error} />
      </section>
    </div>,
    document.body,
  );
}
