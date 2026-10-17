import { usePopupKeyboard } from "./usePopupKeyboard";
import { useEffect, useRef, useState } from "react";
import { useMutation, useIsMutating } from "@tanstack/react-query";
import { api } from "../services/api";
import { ErrorMessage } from "./ui";

export function ShutdownControl({ onStopped }: { onStopped: () => void }) {
  const panel = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const busy = useIsMutating() > 0;
  const stop = useMutation({
    mutationFn: () => api("/app/shutdown", { confirmed: true }),
    onSuccess: onStopped,
  });
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();

    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open]);
  usePopupKeyboard(open, (event) => {
    if (event.key === "Escape") {
      setOpen(false);
      setConfirmed(false);
    }
  });
  return (
    <>
      <button disabled={busy} onClick={() => setOpen(true)}>
        Shut down safely
      </button>
      {open && (
        <div className="modal-backdrop">
          <section
            ref={panel}
            tabIndex={-1}
            className="cleanup-dialog"
            onKeyDown={(event) => {
              if (event.key === "Tab") {
                const items = [
                  ...panel.current!.querySelectorAll<HTMLElement>(
                    "button:not(:disabled), input:not(:disabled)",
                  ),
                ];
                const first = items[0],
                  last = items[items.length - 1];
                if (
                  event.shiftKey &&
                  (document.activeElement === first ||
                    document.activeElement === panel.current)
                ) {
                  event.preventDefault();
                  last?.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                  event.preventDefault();
                  first?.focus();
                }
              }
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Save checkpoint and shut down"
          >
            <h2>Save checkpoint and shut down</h2>
            <p>
              Pause scanning, finish saving completed work, and stop the
              backend. Resume from the saved checkpoint after reopening the app.
              Files still being processed are checked again on resume.
            </p>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={stop.isPending}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              Save my checkpoint and shut down the app
            </label>
            <button
              className="primary"
              disabled={!confirmed || stop.isPending}
              onClick={() => stop.mutate()}
            >
              {stop.isPending
                ? "Saving checkpoint and stopping…"
                : "Confirm shutdown"}
            </button>
            <button
              disabled={stop.isPending}
              onClick={() => {
                setOpen(false);
                setConfirmed(false);
              }}
            >
              Cancel
            </button>
            <ErrorMessage error={stop.error} />
          </section>
        </div>
      )}
    </>
  );
}
