import { useState } from "react";
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
  const [destination, setDestination] = useState<"trash" | "quarantine">(
    "trash",
  );
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
      <h2>Clean up across groups</h2>
      <p>
        Select unwanted files in multiple groups, then preview all selections
        together. Includes selected exact copies and your saved selections in
        similar groups across every page matching the current group filter.
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
          Delete selected across groups
        </button>
      </div>
      <ErrorMessage error={plan.error} />
    </div>
  );
}
