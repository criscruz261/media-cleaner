import { CleanupProgress } from "../components/CleanupProgress";
import { CleanupComparison } from "../components/CleanupComparison";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Undo2, ArrowRight } from "lucide-react";
import { api, bytes, displayLabel } from "../services/api";
import type { Cleanup as CleanupPlan, Page } from "../types/api";
import { Empty, ErrorMessage, Pagination } from "../components/ui";
export function Cleanup({
  plan,
  onComplete,
  embedded = false,
}: {
  plan: CleanupPlan | null;
  onComplete: (result?: CleanupPlan) => void;
  embedded?: boolean;
}) {
  const [confirmed, setConfirmed] = useState(false),
    [offset, setOffset] = useState(0);
  const client = useQueryClient();
  const history = useQuery({
    queryKey: ["cleanup-history", offset],
    queryFn: () =>
      api<Page<CleanupPlan>>(`/cleanup/history?offset=${offset}&limit=10`),
    enabled: !embedded,
  });
  const execute = useMutation({
    mutationFn: () =>
      api<CleanupPlan>("/cleanup/execute", {
        plan_id: plan?.id,
        token: plan?.token,
        confirmed,
      }),
    onSuccess: (result) => {
      onComplete(result);
      setConfirmed(false);
      client.invalidateQueries();
    },
  });
  const restore = useMutation({
    mutationFn: (id: string) =>
      api(`/cleanup/${id}/restore`, { confirmed: true }),
    onSuccess: () => client.invalidateQueries(),
  });
  if (execute.isPending && plan) {
    return <CleanupProgress planId={plan.id} total={plan.items.length} />;
  }
  return (
    <>
      {!embedded && (
        <div className="page-heading">
          <div>
            <div className="eyebrow">A second look, before you clean</div>
            <h1>Make room, safely.</h1>
            <p>Review every move. Keep a recovery record.</p>
          </div>
        </div>
      )}
      {plan && (
        <section className="panel cleanup-plan">
          <div className="section-heading">
            <h2>
              <ShieldCheck size={20} /> Dry-run cleanup preview
            </h2>
            <span className="badge">No files moved yet</span>
          </div>
          <p className="notice">
            Review scope:{" "}
            {plan.items.every(
              (item) => item.classification === "EXACT_DUPLICATE",
            )
              ? "Exact duplicates only"
              : plan.items.every(
                    (item) => item.classification === "SIMILAR_CONTENT",
                  )
                ? "Similar media only"
                : "Selected groups"}
            . Only the files shown below are included in this cleanup.
          </p>
          <p>
            <strong>
              {plan.items.length} files · {bytes(plan.total_bytes)}
            </strong>{" "}
            will move to{" "}
            <strong>
              {plan.destination === "trash"
                ? "your operating system’s Trash / Recycle Bin"
                : "quarantine on the same storage volume"}
            </strong>
            .
          </p>
          <p className="muted">
            This preview expires at{" "}
            {new Date(plan.expires_at).toLocaleTimeString()}. Selected files and
            any retained copies will be rehashed before cleanup. Trash failures
            are reported; there is no fallback to permanent deletion.
          </p>
          {plan.items.some(
            (item) => item.classification === "SIMILAR_CONTENT",
          ) && (
            <div className="notice">
              <p>
                These media files look similar but may contain different moments
                or audio. This is your manual removal choice, not proof they are
                duplicates. Compare the full images or playback and sound before
                confirming.
              </p>
            </div>
          )}
          <CleanupComparison plan={plan} />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />{" "}
            I reviewed these files and confirm moving them to {plan.destination}
            .
          </label>
          <button
            className="primary"
            disabled={!confirmed || execute.isPending}
            onClick={() => execute.mutate()}
          >
            {execute.isPending ? "Validating and moving…" : "Confirm cleanup"}{" "}
            <ArrowRight size={15} />
          </button>
          <ErrorMessage error={execute.error} />
        </section>
      )}
      {!embedded && !plan && (
        <Empty title="Nothing queued for cleanup">
          Uncheck unwanted files in Duplicate review, then choose Preview
          cleanup.
        </Empty>
      )}
      {!embedded && (
        <section className="panel">
          <h2>Cleanup & recovery history</h2>
          <p className="muted">
            Restore quarantined files here. For Trash operations, use your
            operating system’s Trash / Recycle Bin.
          </p>
          {history.data?.items.map((operation) => (
            <details className="operation" key={operation.id}>
              <summary>
                {new Date(operation.created_at).toLocaleString()} ·{" "}
                {operation.items.length} files · {operation.destination}{" "}
                <span className="badge">{displayLabel(operation.status)}</span>
              </summary>
              {operation.items.map((item) => (
                <div className="operation-item" key={item.file_id}>
                  <p>{item.source}</p>
                  <small>
                    {displayLabel(item.status)}
                    {item.quarantine_path
                      ? ` · Recovery: ${item.quarantine_path}`
                      : ""}
                  </small>
                  {item.error && <p className="error">{item.error}</p>}
                </div>
              ))}
              {operation.destination === "quarantine" &&
                ["completed", "partial", "interrupted"].includes(
                  operation.status,
                ) && (
                  <button
                    disabled={restore.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Restore quarantined files to their original paths? Existing files will not be overwritten.",
                        )
                      )
                        restore.mutate(operation.id);
                    }}
                  >
                    <Undo2 size={14} /> Restore quarantined files
                  </button>
                )}
            </details>
          ))}
          <ErrorMessage error={history.error || restore.error} />
          <Pagination
            offset={offset}
            total={history.data?.total ?? 0}
            size={10}
            onChange={setOffset}
          />
        </section>
      )}
    </>
  );
}
