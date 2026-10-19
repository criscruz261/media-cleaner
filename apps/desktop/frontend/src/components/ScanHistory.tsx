import { useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, displayLabel } from "../services/api";
import type { Page, Scan } from "../types/api";
import { ErrorMessage, Loading, Pagination } from "./ui";

export function ScanHistory({
  scanId,
  selectScan,
}: {
  scanId: string;
  selectScan: (id: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [deleteFailure, setDeleteFailure] = useState<{
    message: string;
  } | null>(null);
  useEffect(() => {
    if (!deleteFailure) return;
    const timer = window.setTimeout(() => setDeleteFailure(null), 3000);
    return () => window.clearTimeout(timer);
  }, [deleteFailure]);
  const confirmation = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (confirming) confirmation.current?.showModal?.();
  }, [confirming]);
  const client = useQueryClient();
  const history = useQuery({
    queryKey: ["scans", "history", offset],
    queryFn: () => api<Page<Scan>>(`/scans?offset=${offset}&limit=20`),
  });
  const favorite = useMutation({
    mutationFn: (scan: Scan) =>
      api(`/scans/${scan.id}/favorite`, { favorite: !scan.favorite }),
    onSuccess: async (_, scan) => {
      setSelected((ids) => ids.filter((id) => id !== scan.id));
      await client.invalidateQueries();
    },
  });
  const remove = useMutation({
    onMutate: async () => {
      setDeleteFailure(null);
      await client.cancelQueries({ queryKey: ["scans"] });
    },
    onError: (error: Error) => setDeleteFailure({ message: error.message }),
    mutationFn: () =>
      api<{ deleted_ids: string[] }>("/scans/history/delete", {
        scan_ids: selected,
        confirmed: true,
      }),
    onSuccess: async (result) => {
      setDeleteFailure(null);
      const deleted = new Set(result.deleted_ids);
      client.setQueriesData<Page<Scan>>({ queryKey: ["scans"] }, (page) => {
        if (!page?.items) return page;
        return {
          ...page,
          items: page.items.filter((scan) => !deleted.has(scan.id)),
          total: Math.max(0, page.total - deleted.size),
        };
      });
      if (result.deleted_ids.includes(scanId)) selectScan("");
      setSelected([]);
      setConfirming(false);
      setOffset(0);
      await client.invalidateQueries({ queryKey: ["scans"] });
    },
  });
  const busy = favorite.isPending || remove.isPending;
  const eligibleIds = (history.data?.items ?? [])
    .filter(
      (scan) => !scan.favorite && !["queued", "running"].includes(scan.status),
    )
    .map((scan) => scan.id);
  const allChecked =
    eligibleIds.length > 0 && eligibleIds.every((id) => selected.includes(id));
  return (
    <section className="panel scan-history" aria-label="Scan history">
      <div className="scan-history-heading">
        <h2>Scan history</h2>
        <span className="hint">Check scans to delete their history</span>
      </div>
      <p className="hint">
        Deleting history removes it from the history list. Media files, cached
        analysis, and cleanup recovery records are preserved. Favorites are
        protected from deletion.
      </p>
      {history.isPending && <Loading />}
      <div className="scan-history-table-scroll">
        <table className="scan-history-table">
          <thead>
            <tr>
              <th scope="col">
                <input
                  type="checkbox"
                  aria-label="Select all eligible scans on this page"
                  checked={allChecked}
                  ref={(node) => {
                    if (node)
                      node.indeterminate = selected.length > 0 && !allChecked;
                  }}
                  disabled={!eligibleIds.length || busy || confirming}
                  onChange={(event) =>
                    setSelected(event.target.checked ? eligibleIds : [])
                  }
                />
              </th>
              <th scope="col">Date / time</th>
              <th scope="col">Status</th>
              <th scope="col">Scan ID</th>
              <th scope="col">Directories scanned</th>
              <th scope="col">
                <div className="scan-history-action-heading">
                  <span>Actions</span>
                  <button
                    className="scan-history-delete"
                    disabled={!selected.length || busy || confirming}
                    onClick={() => setConfirming(true)}
                  >
                    <Trash2 size={14} aria-hidden="true" /> Delete (
                    {selected.length})
                  </button>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {history.data?.items.map((scan) => {
              const protectedScan =
                !!scan.favorite || ["queued", "running"].includes(scan.status);
              return (
                <tr className="scan-history-row" key={scan.id}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Select scan ${scan.id}`}
                      checked={selected.includes(scan.id)}
                      disabled={protectedScan || busy || confirming}
                      onChange={(event) =>
                        setSelected((ids) =>
                          event.target.checked
                            ? [...ids, scan.id]
                            : ids.filter((id) => id !== scan.id),
                        )
                      }
                    />
                  </td>
                  <td>
                    <time dateTime={scan.created_at}>
                      {new Date(scan.created_at).toLocaleString()}
                    </time>
                  </td>
                  <td>{displayLabel(scan.status)}</td>
                  <td title={scan.id}>
                    <code>{scan.id.slice(0, 8)}</code>
                  </td>
                  <td>
                    <span
                      className="hint scan-history-roots"
                      title={scan.options.roots.join(", ")}
                    >
                      {scan.options.roots.join(", ")}
                    </span>
                  </td>
                  <td>
                    <div className="actions">
                      <button
                        disabled={busy || confirming}
                        onClick={() => selectScan(scan.id)}
                      >
                        Review scan
                      </button>
                      <button
                        aria-label={`${scan.favorite ? "Unfavorite" : "Favorite"} scan ${scan.id}`}
                        aria-pressed={!!scan.favorite}
                        disabled={busy || confirming}
                        onClick={() => favorite.mutate(scan)}
                      >
                        {scan.favorite ? "★" : "☆"}
                      </button>
                      <button
                        className="scan-history-delete"
                        aria-label={`Delete scan ${scan.id}`}
                        title={
                          scan.favorite
                            ? "Unfavorite this scan to delete its history"
                            : ["queued", "running"].includes(scan.status)
                              ? "Pause or stop this scan before deleting its history"
                              : "Delete this scan history"
                        }
                        disabled={protectedScan || busy || confirming}
                        onClick={() => {
                          setSelected([scan.id]);
                          setConfirming(true);
                        }}
                      >
                        <Trash2 size={14} aria-hidden="true" /> Delete
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {history.data?.total === 0 && <p>No scan history.</p>}
      <Pagination
        offset={offset}
        total={history.data?.total ?? 0}
        size={20}
        onChange={(next) => {
          setOffset(next);
          setSelected([]);
          setConfirming(false);
        }}
      />
      {confirming ? (
        <dialog
          ref={confirmation}
          className="scan-history-confirm"
          aria-labelledby="delete-history-title"
          onCancel={(event) => {
            event.preventDefault();
            if (!busy) setConfirming(false);
          }}
        >
          <h2 id="delete-history-title">Delete scan history?</h2>
          <p>
            Delete {selected.length} selected scan history entries? Their saved
            review results will leave the history list.
          </p>
          <button disabled={busy} onClick={() => setConfirming(false)}>
            Cancel
          </button>{" "}
          <button
            className="scan-history-delete"
            disabled={busy}
            onClick={() => remove.mutate()}
          >
            {remove.isPending ? "Deleting…" : "Confirm delete history"}
          </button>
        </dialog>
      ) : null}
      {deleteFailure && (
        <div role="alert" className="scan-history-error-toast">
          Could not delete scan history: {deleteFailure.message}
        </div>
      )}
      <ErrorMessage error={history.error || favorite.error} />
    </section>
  );
}
