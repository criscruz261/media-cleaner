import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { ErrorMessage } from "./ui";

export function ClearDeletionSelections({ scanId }: { scanId: string }) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const client = useQueryClient();
  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);
  const clear = useMutation({
    mutationFn: () =>
      api(`/scans/${scanId}/clear-deletion-selections`, { confirmed: true }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["group"] }),
        client.invalidateQueries({ queryKey: ["groups"] }),
        client.invalidateQueries({ queryKey: ["selection-summary"] }),
      ]);
      setOpen(false);
    },
  });
  return (
    <>
      <button
        className="action-keep clear-deletion-selections"
        onClick={() => {
          clear.reset();
          setOpen(true);
        }}
      >
        Clear deletion selections
      </button>
      {open && (
        <dialog
          ref={dialog}
          className="scan-history-confirm"
          aria-labelledby="clear-selection-title"
          onCancel={(event) => {
            event.preventDefault();
            if (!clear.isPending) setOpen(false);
          }}
        >
          <h2 id="clear-selection-title">Clear deletion selections?</h2>
          <p>
            Keep all files in this scan by clearing deletion selections across
            every group and page, including groups hidden by the current filter.
            Your saved analysis is preserved.
          </p>
          <div className="confirmation-actions">
            <button disabled={clear.isPending} onClick={() => setOpen(false)}>
              Cancel
            </button>{" "}
            <button
              className="action-keep"
              disabled={clear.isPending}
              onClick={() => clear.mutate()}
            >
              {clear.isPending ? "Clearing…" : "Confirm clear selections"}
            </button>
          </div>
          <ErrorMessage error={clear.error} />
        </dialog>
      )}
    </>
  );
}
