import { useCleanupDestination } from "./CleanupDestinationContext";
import { useMutation, useIsMutating } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Cleanup } from "../types/api";
import { ErrorMessage } from "./ui";

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
  const plan = useMutation({
    mutationFn: () =>
      api<Cleanup>("/cleanup/plan-selected", {
        scan_id: scanId,
        destination,
        ...(classification ? { classification } : {}),
      }),
    onSuccess: (preview) => onPlan(preview),
  });
  return (
    <div className="panel">
      <h2>Review groups before deletion</h2>
      <p>
        Review kept files and selected deletions in groups matching your current
        filter, across all pages. Nothing is moved until you confirm in the
        review window.
      </p>
      <p>
        Scope:{" "}
        {classification === "EXACT_DUPLICATE"
          ? "Exact duplicates only"
          : classification === "SIMILAR_CONTENT"
            ? "Similar media only"
            : "All matches"}
        . Checkbox changes are saved automatically. Exact-copy defaults are
        included; similar media requires your selection.
      </p>
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
          className="primary"
          disabled={!scanId || pendingChanges > 0}
          onClick={() => plan.mutate()}
        >
          {plan.isPending
            ? "Preparing review…"
            : classification === "EXACT_DUPLICATE"
              ? "Review exact duplicate groups"
              : classification === "SIMILAR_CONTENT"
                ? "Review similar media groups"
                : "Review selected groups"}
        </button>
      </div>
      <ErrorMessage error={plan.error} />
    </div>
  );
}
