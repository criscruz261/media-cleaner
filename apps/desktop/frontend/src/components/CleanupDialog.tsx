import { displayLabel } from "../services/api";
import { usePopupKeyboard } from "./usePopupKeyboard";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useIsMutating } from "@tanstack/react-query";
import { Cleanup } from "../pages/Cleanup";
import type { Cleanup as CleanupPlan } from "../types/api";

export function CleanupDialog({
  plan,
  onClose,
}: {
  plan: CleanupPlan;
  onClose: () => void;
}) {
  const [result, setResult] = useState<CleanupPlan | null>(null);
  const busy = useIsMutating() > 0;
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();

    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  usePopupKeyboard(true, (event) => {
    if (event.key === "Escape") onClose();
  });
  return createPortal(
    <div
      className="modal-backdrop"
      onClick={() => {
        if (!busy) onClose();
      }}
    >
      <section
        className="cleanup-dialog"
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Review and confirm deletion"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "Tab") {
            const items = [
              ...panel.current!.querySelectorAll<HTMLElement>(
                "button:not(:disabled), input:not(:disabled), summary",
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
      >
        <button
          className="cleanup-dialog-close"
          disabled={busy}
          onClick={onClose}
        >
          {result ? "Done" : "Cancel"}
        </button>
        {result ? (
          <div role="status">
            <h2>
              {result.status === "completed"
                ? "Cleanup completed"
                : "Cleanup needs attention"}
            </h2>
            {result.items.map((item) => (
              <p key={item.file_id}>
                {item.source} · {displayLabel(item.status)}
                {item.error && <span className="error"> · {item.error}</span>}
              </p>
            ))}
            <p>
              You can continue reviewing this scan. Recovery records are
              available in Cleanup.
            </p>
          </div>
        ) : (
          <Cleanup
            plan={plan}
            embedded
            onComplete={(outcome) => {
              if (outcome) setResult(outcome);
            }}
          />
        )}
      </section>
    </div>,
    document.body,
  );
}
