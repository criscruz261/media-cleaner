import { useCleanupDestination } from "./CleanupDestinationContext";
import { useMutation, useIsMutating } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Cleanup } from "../types/api";
import { ErrorMessage } from "./ui";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function BatchCleanup({
  scanId,
  onPlan,
  classification = "",
}: {
  scanId: string;
  classification?: "" | "EXACT_DUPLICATE" | "SIMILAR_CONTENT";
  onPlan: (plan: Cleanup) => void;
}) {
  const [destination, setDestination] = useCleanupDestination();
  const pendingChanges = useIsMutating();
  const originalButton = useRef<HTMLButtonElement>(null);
  const [stickyTarget, setStickyTarget] = useState<HTMLElement | null>(null);
  const [showSticky, setShowSticky] = useState(false);
  useEffect(() => {
    let target: HTMLElement | null = null;
    const update = () => {
      const current = document.getElementById("sticky-review-action");
      if (current !== target) {
        target = current;
        setStickyTarget(current);
      }
      const rect = originalButton.current?.getBoundingClientRect();
      const banner = target
        ?.closest(".sticky-review-progress")
        ?.getBoundingClientRect();
      setShowSticky(
        !!target &&
          !!rect &&
          (rect.top < (banner?.bottom ?? 0) ||
            rect.bottom > window.innerHeight),
      );
    };
    // The banner loads asynchronously; attach even if its action slot is not ready yet.
    const mutations = new MutationObserver(update);
    mutations.observe(document.body, { childList: true, subtree: true });
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    if (originalButton.current) observer?.observe(originalButton.current);
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    update();
    return () => {
      mutations.disconnect();
      observer?.disconnect();
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [scanId]);
  const plan = useMutation({
    mutationFn: () =>
      api<Cleanup>("/cleanup/plan-selected", {
        scan_id: scanId,
        destination,
        ...(classification ? { classification } : {}),
      }),
    onSuccess: (preview) => onPlan(preview),
  });
  const reviewLabel = plan.isPending
    ? "Preparing review…"
    : classification === "EXACT_DUPLICATE"
      ? "Review exact duplicate groups"
      : classification === "SIMILAR_CONTENT"
        ? "Review similar media groups"
        : "Review selected groups";
  return (
    <div className="panel batch-cleanup">
      <div className="batch-cleanup-summary">
        <h2>Review groups before deletion</h2>
        <p>
          Scope:{" "}
          {classification === "EXACT_DUPLICATE"
            ? "Exact duplicates only"
            : classification === "SIMILAR_CONTENT"
              ? "Similar media only"
              : "All matches"}
          {" · All pages · Confirmation required"}
        </p>
      </div>
      <div className="group-actions">
        <select
          aria-label="Batch cleanup destination"
          value={destination}
          onChange={(event) =>
            setDestination(event.target.value as typeof destination)
          }
        >
          <option value="trash">OS Trash / Recycle Bin</option>
          <option value="quarantine">Same-volume quarantine</option>
        </select>
        <button
          ref={originalButton}
          className="primary"
          disabled={!scanId || pendingChanges > 0}
          onClick={() => plan.mutate()}
        >
          {reviewLabel}
        </button>
      </div>
      <ErrorMessage error={plan.error} />
      {showSticky &&
        stickyTarget &&
        createPortal(
          <div>
            <button
              className="primary"
              disabled={!scanId || pendingChanges > 0}
              onClick={() => plan.mutate()}
            >
              {reviewLabel}
            </button>
            <ErrorMessage error={plan.error} />
          </div>,
          stickyTarget,
        )}
    </div>
  );
}
