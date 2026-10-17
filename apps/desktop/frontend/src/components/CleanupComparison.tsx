import { useState } from "react";
import type { Cleanup, CleanupItem, CleanupReviewFile } from "../types/api";
import { bytes, prefix } from "../services/api";

function FileCard({ file }: { file: CleanupReviewFile }) {
  const [failed, setFailed] = useState(false);
  return (
    <article className="cleanup-review-file">
      {file.id && !failed ? (
        <img
          loading="lazy"
          src={`${prefix}/files/${file.id}/thumbnail`}
          alt={file.name}
          onError={() => setFailed(true)}
        />
      ) : (
        <p className="muted">Thumbnail unavailable</p>
      )}
      <strong>{file.name}</strong>
      <span>{bytes(file.size)}</span>
      <small>{file.path}</small>
    </article>
  );
}

export function CleanupComparison({ plan }: { plan: Cleanup }) {
  const groups = new Map<string, CleanupItem[]>();
  const deleted = new Set(plan.items.map((item) => item.file_id));
  for (const item of plan.items) {
    const key = item.group_id ?? item.keeper ?? item.file_id;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return (
    <div className="cleanup-review-groups" aria-label="Read-only group review">
      <p>
        Read-only preview of this cleanup plan. Cancel to change selections in
        Duplicate review.
      </p>
      {[...groups.entries()].map(([id, items], index) => {
        const snapshot = items.find((item) => item.review_files)?.review_files;
        const deleting =
          snapshot?.filter((file) => deleted.has(file.id)) ??
          items.map((item) => ({
            id: item.file_id,
            name: item.source.split(/[\\/]/).pop() ?? item.source,
            path: item.source,
            size: item.size,
            media_type: "",
          }));
        const keptPaths = [
          ...new Set(
            items.flatMap((item) => (item.keeper ? [item.keeper] : [])),
          ),
        ];
        const kept =
          snapshot?.filter((file) => !deleted.has(file.id)) ??
          keptPaths.map((path) => ({
            id: "",
            name: path.split(/[\\/]/).pop() ?? path,
            path,
            size: 0,
            media_type: "",
          }));
        return (
          <section
            key={id}
            className="cleanup-review-group"
            aria-label={`Cleanup group ${index + 1}`}
          >
            <h3>
              Group {index + 1} ·{" "}
              {items[0].classification === "EXACT_DUPLICATE"
                ? "Exact duplicates"
                : items[0].classification === "SIMILAR_CONTENT"
                  ? "Similar media"
                  : "Selected media"}
            </h3>
            <p className="hint group-identifier">Group {id}</p>
            <div className="cleanup-review-columns">
              <section
                className="cleanup-review-kept"
                aria-label="Files to keep"
              >
                <h4>Keep · {kept.length}</h4>
                {kept.length ? (
                  kept.map((file) => (
                    <FileCard key={file.id || file.path} file={file} />
                  ))
                ) : (
                  <p>No files will be kept in this group.</p>
                )}
              </section>
              <section
                className="cleanup-review-deleted"
                aria-label="Files to delete"
              >
                <h4>Delete · {deleting.length}</h4>
                {deleting.map((file) => (
                  <FileCard key={file.id} file={file} />
                ))}
              </section>
            </div>
          </section>
        );
      })}
    </div>
  );
}
