import { GroupPreview } from "../components/GroupPreview";
import { BatchCleanup } from "../components/BatchCleanup";
import { VideoCompare } from "../components/VideoCompare";
import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ShieldCheck, ArrowRight, Layers3 } from "lucide-react";
import { api, bytes } from "../services/api";
import type { Scan, Page, Group, Cleanup, Settings } from "../types/api";
import { Empty, ErrorMessage, Loading, Pagination } from "../components/ui";
import { MediaPreview } from "../components/MediaPreview";
export function Review({
  scanId,
  selectScan,
  onPlan,
  navigate,
}: {
  scanId: string;
  selectScan: (id: string) => void;
  onPlan: (plan: Cleanup) => void;
  navigate: (page: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const scans = useQuery({
    queryKey: ["scans"],
    queryFn: () => api<Page<Scan>>("/scans?limit=100"),
  });
  const groups = useQuery({
    queryKey: ["groups", scanId, offset],
    queryFn: () =>
      api<Page<Group>>(`/groups?scan_id=${scanId}&offset=${offset}&limit=10`),
    enabled: !!scanId,
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">LESS GUESSWORK, MORE CONTROL</div>
          <h1>Review the repeats.</h1>
          <p>Exact copies and similar media. You decide what stays.</p>
        </div>
        <select
          aria-label="Choose scan to review"
          value={scanId}
          onChange={(e) => {
            selectScan(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Choose a scan</option>
          {scans.data?.items.map((scan) => (
            <option value={scan.id} key={scan.id}>
              {new Date(scan.created_at).toLocaleString()} · {scan.status}
            </option>
          ))}
        </select>
      </div>
      <div className="notice">
        <ShieldCheck size={18} />
        <p>
          Exact copies and approximate media matches are labeled separately.
          Similar groups keep everything selected until you review them. A file
          may appear in both an exact and a similar group. Copy-name
          recommendations are advisory. RAW originals, protected folders, and
          potential photo/video companions stay protected.
        </p>
      </div>
      {scanId && <BatchCleanup scanId={scanId} onPlan={onPlan} />}
      {!scanId ? (
        <Empty title="Choose a scan to review">
          <button onClick={() => navigate("Scanner")}>
            Go to scanner <ArrowRight size={14} />
          </button>
        </Empty>
      ) : groups.isPending ? (
        <Loading />
      ) : !groups.data?.items.length ? (
        <Empty title="No exact-match groups">
          Run a similar-media scan or choose a completed scan above. Video
          content similarity is not included yet.
        </Empty>
      ) : (
        groups.data.items.map((group) => (
          <GroupCard
            key={group.id}
            group={group}
            onPlan={onPlan}
            thumbnailFirst
          />
        ))
      )}
      <ErrorMessage error={groups.error} />
      <Pagination
        offset={offset}
        total={groups.data?.total ?? 0}
        size={10}
        onChange={setOffset}
      />
    </>
  );
}
export function GroupCard({
  group,
  onPlan,
  thumbnailFirst = false,
  selectForDeletion = false,
  live = false,
}: {
  group: Group;
  onPlan: (plan: Cleanup) => void;
  thumbnailFirst?: boolean;
  selectForDeletion?: boolean;
  live?: boolean;
}) {
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0),
    [destination, setDestination] = useState<"trash" | "quarantine">("trash");
  const client = useQueryClient();
  const preferences = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  useEffect(() => {
    if (preferences.data) setDestination(preferences.data.cleanup_destination);
  }, [preferences.data?.cleanup_destination]);
  const detail = useQuery({
    queryKey: ["group", group.id, offset],
    refetchInterval: live ? 1000 : false,
    queryFn: () =>
      api<Group & { files: NonNullable<Group["files"]> }>(
        `/groups/${group.id}?offset=${offset}&limit=50`,
      ),
  });
  const review = useMutation({
    mutationFn: ({ id, keep }: { id: string; keep: boolean }) =>
      api(`/groups/${group.id}/review`, { changes: { [id]: keep } }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["group", group.id] }),
  });
  const selectAll = useMutation({
    mutationFn: () => api(`/groups/${group.id}/review`, { keep_ids: [] }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["group", group.id] }),
  });
  const eligible =
    detail.data?.files.filter(
      (file) => !file.keep && file.status === "ready",
    ) ?? [];
  const plan = useMutation({
    mutationFn: async () => {
      const files = [];
      for (let start = 0; ; start += 200) {
        const page = await api<Group & { files: NonNullable<Group["files"]> }>(
          `/groups/${group.id}?offset=${start}&limit=200`,
        );
        files.push(
          ...page.files.filter((file) => !file.keep && file.status === "ready"),
        );
        if (page.files.length < 200) break;
      }
      return api<Cleanup>("/cleanup/plan", {
        file_ids: files.map((file) => file.id),
        destination,
        group_id: group.id,
      });
    },
    onSuccess: onPlan,
  });
  return (
    <article className="panel group-card">
      {previewId && (
        <GroupPreview
          groupId={group.id}
          initialId={previewId}
          onClose={() => setPreviewId(null)}
        />
      )}
      <div className="section-heading">
        <div>
          <h2>
            <Layers3 size={18} /> {group.member_count}{" "}
            {group.classification === "EXACT_DUPLICATE"
              ? "exact copies"
              : group.evidence.media_kind === "sequence"
                ? "similar videos / animations"
                : "similar photos"}
          </h2>
          <span className="badge exact">
            {group.classification === "EXACT_DUPLICATE"
              ? "EXACT DUPLICATE"
              : "SIMILAR MEDIA · REVIEW REQUIRED"}
          </span>
        </div>
        <strong>{bytes(group.recoverable)} potential</strong>
      </div>
      {detail.data?.files.some((file) => file.media_type === "video") && (
        <VideoCompare groupId={group.id} />
      )}
      <p className="recommendation">{group.recommendation}</p>
      <details className="evidence">
        <summary>
          Matching evidence ·{" "}
          {group.classification === "EXACT_DUPLICATE"
            ? "SHA-256"
            : group.evidence.media_kind === "sequence"
              ? "time-spaced frames"
              : "pHash + dHash"}
        </summary>
        {group.classification === "EXACT_DUPLICATE" ? (
          <>
            <code>{group.evidence.sha256}</code>
            <p>
              Same file size and complete SHA-256 digest. Algorithm:{" "}
              {group.evidence.algorithm}.
            </p>
          </>
        ) : group.evidence.media_kind === "sequence" ? (
          <>
            <p>
              At least {group.evidence.minimum_matched_samples} of{" "}
              {group.evidence.sample_count} time-spaced visual samples match for
              each pair. Maximum duration difference:{" "}
              {group.evidence.max_duration_difference_seconds?.toFixed(3)}{" "}
              seconds.
            </p>
            <p>
              Frame pHash limit: {group.evidence.phash_limit}/64; dHash limit:{" "}
              {group.evidence.dhash_limit}/64. Every group pair qualifies.{" "}
              {group.evidence.note}
            </p>
          </>
        ) : (
          <>
            <p>
              Maximum pairwise pHash distance:{" "}
              {group.evidence.max_phash_distance}/64 (limit{" "}
              {group.evidence.phash_limit}). Maximum dHash distance:{" "}
              {group.evidence.max_dhash_distance}/64 (limit{" "}
              {group.evidence.dhash_limit}).
            </p>
            <p>
              Every member passes both thresholds against every other member,
              with aspect and color checks. {group.evidence.note}
            </p>
          </>
        )}
      </details>
      {detail.isPending ? (
        <Loading />
      ) : (
        <div className="media-grid">
          {detail.data?.files.map((file) => (
            <div
              className={`media-card ${file.keep ? "kept" : ""}`}
              key={file.id}
            >
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={selectForDeletion ? !file.keep : file.keep}
                  disabled={
                    review.isPending ||
                    selectAll.isPending ||
                    plan.isPending ||
                    !!file.protected_reason ||
                    file.status !== "ready"
                  }
                  onChange={(e) =>
                    review.mutate({
                      id: file.id,
                      keep: selectForDeletion
                        ? !e.target.checked
                        : e.target.checked,
                    })
                  }
                />
                <Check size={14} />{" "}
                {selectForDeletion ? "Select for deletion" : "Keep this file"}
              </label>
              <MediaPreview
                file={file}
                thumbnailFirst={thumbnailFirst}
                onOpen={() => setPreviewId(file.id)}
              />
              <strong className="filename">{file.name}</strong>
              <p className="file-path">{file.path}</p>
              <div className="file-meta">
                <span>{bytes(file.size)}</span>
                {!!file.metadata.width && (
                  <span>
                    {String(file.metadata.width)} ×{" "}
                    {String(file.metadata.height)}
                  </span>
                )}
                {file.id === group.recommended_id && (
                  <span>Suggested keeper</span>
                )}
              </div>
              {file.protected_reason && (
                <p className="protected">
                  <ShieldCheck size={12} />
                  {file.protected_reason}
                </p>
              )}
              {file.status !== "ready" && (
                <p className="muted">{file.status}</p>
              )}
              {file.warnings.map((warning) => (
                <p className="hint" key={warning}>
                  {warning}
                </p>
              ))}
            </div>
          ))}
        </div>
      )}
      <Pagination
        offset={offset}
        total={group.member_count}
        size={50}
        onChange={setOffset}
      />
      <p className="hint">
        {selectForDeletion
          ? "Select the unwanted files, then click Delete selected for this group. Unselected files are kept."
          : "Check the files to keep. Uncheck unwanted files, then preview deletion for this group."}{" "}
        The preview includes selected files across all pages of this group. You
        must confirm before anything is moved.
      </p>
      <div className="group-actions">
        <button
          disabled={
            !detail.data ||
            selectAll.isPending ||
            review.isPending ||
            plan.isPending
          }
          onClick={() => selectAll.mutate()}
        >
          Select all for deletion (keep none)
        </button>
        <div>
          <label htmlFor={`destination-${group.id}`}>Cleanup destination</label>
          <select
            id={`destination-${group.id}`}
            value={destination}
            onChange={(e) =>
              setDestination(e.target.value as typeof destination)
            }
          >
            <option value="trash">OS Trash / Recycle Bin</option>
            <option value="quarantine">Same-volume quarantine</option>
          </select>
        </div>
        <button
          className="primary"
          disabled={
            !eligible.length ||
            plan.isPending ||
            review.isPending ||
            selectAll.isPending
          }
          onClick={() => plan.mutate()}
        >
          {selectForDeletion ? "Delete selected" : "Delete unchecked"} ·{" "}
          {eligible.length} on this page <ArrowRight size={15} />
        </button>
      </div>
      <ErrorMessage
        error={detail.error || review.error || selectAll.error || plan.error}
      />
    </article>
  );
}
