import { ScannerResetContext } from "./ScannerResetContext";
import { useContext } from "react";
import { GroupFilterContext } from "./GroupFilters";
import { ErrorMessage } from "./ui";
import {
  useQuery,
  useMutation,
  useQueryClient,
  useIsMutating,
} from "@tanstack/react-query";
import { api } from "../services/api";
import type { Scan } from "../types/api";

export function ScanProgress({
  scanId,
  reviewAction = false,
}: {
  scanId: string;
  reviewAction?: boolean;
}) {
  const client = useQueryClient();
  const resetScanner = useContext(ScannerResetContext);
  const classification = useContext(GroupFilterContext)?.[0] ?? "";
  const selection = useQuery({
    queryKey: ["selection-summary", scanId, classification],
    queryFn: () =>
      api<{ selected_files: number; total_files: number }>(
        `/scans/${scanId}/selection-summary${classification ? `?classification=${classification}` : ""}`,
      ),
    enabled: !!scanId,
    refetchInterval: 1000,
  });
  const busy = useIsMutating() > 0;
  const control = useMutation({
    mutationFn: (action: string) => api(`/scans/${scanId}/${action}`, {}),
    onSuccess: (_, action) => {
      void client.invalidateQueries();
      if (action === "stop") resetScanner?.();
    },
  });
  const scan = useQuery({
    queryKey: ["review-scan-progress", scanId],
    queryFn: () => api<Scan>(`/scans/${scanId}`),
    enabled: !!scanId,
    refetchInterval: (query) =>
      ["running", "queued"].includes(query.state.data?.status ?? "")
        ? 1000
        : 5000,
  });
  if (!scanId) return null;
  const value = scan.data;
  const active = ["running", "queued"].includes(value?.status ?? "");
  return (
    <div className="review-scan-progress" role="status" aria-live="polite">
      {value ? (
        <>
          <strong>
            Scan {value.status} · {value.processed} / {value.discovered} files
            processed
          </strong>
          <progress
            aria-label="Scan progress during review"
            max={Math.max(1, value.discovered)}
            value={value.stage === "discovery" ? undefined : value.processed}
          />
          <strong className="selection-summary">
            {selection.data
              ? `${selection.data.selected_files} / ${selection.data.total_files} files selected for deletion`
              : selection.isError
                ? "Deletion selection count unavailable"
                : "Loading deletion selection count…"}
            <small>
              {classification === "EXACT_DUPLICATE"
                ? "Exact duplicates only"
                : classification === "SIMILAR_CONTENT"
                  ? "Similar media only"
                  : "All matching groups"}{" "}
              · all pages
            </small>
          </strong>
          {reviewAction && <div id="sticky-review-action" />}
          {active && (
            <button
              disabled={busy}
              onClick={() => control.mutate("checkpoint")}
            >
              {control.isPending && control.variables === "checkpoint"
                ? "Saving checkpoint…"
                : "Pause & save checkpoint"}
            </button>
          )}
          {["paused", "interrupted", "failed"].includes(value.status) && (
            <button
              disabled={busy || value.stage === "Saving checkpoint"}
              onClick={() => control.mutate("resume")}
            >
              Resume from checkpoint
            </button>
          )}
          {(active || ["paused", "interrupted"].includes(value.status)) && (
            <button
              disabled={busy}
              onClick={() => control.mutate("stop")}
              title="End this scan after saving completed work. Results remain available; start a new scan to scan again."
            >
              {control.isPending && control.variables === "stop"
                ? "Stopping & saving…"
                : "Stop scan"}
            </button>
          )}
          {value.checkpoint_at && (
            <small>
              Checkpoint: {new Date(value.checkpoint_at).toLocaleTimeString()}
            </small>
          )}
          <ErrorMessage error={control.error} />
          <span>
            {active
              ? "Scanning continues. New groups appear at the end; existing groups may still gain files."
              : value.status === "completed"
                ? "Scan complete."
                : value.status === "cancelled"
                  ? "Scan stopped. Saved results remain available; start a new scan to scan again."
                  : "Saved results. Groups may change when the scan resumes."}
          </span>
        </>
      ) : (
        <span>
          {scan.isError
            ? "Scan progress unavailable. Saved results remain available."
            : "Loading scan progress…"}
        </span>
      )}
    </div>
  );
}
