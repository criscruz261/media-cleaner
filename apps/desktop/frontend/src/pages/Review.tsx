import { useCleanupDestination } from "../components/CleanupDestinationContext";
import { groupPage } from "../services/groupPages";
import { GroupFilters, useGroupFilter } from "../components/GroupFilters";
import { GroupPreview, PreviewContext } from "../components/GroupPreview";
import { BatchCleanup } from "../components/BatchCleanup";
import { VideoCompare } from "../components/VideoCompare";
import { useState, useContext } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ShieldCheck, ArrowRight, Layers3 } from "lucide-react";
import { api, bytes, displayLabel } from "../services/api";
import type { Scan, Page, Group, Cleanup } from "../types/api";
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
  const [pageSize, setPageSize] = useState(10);
  const [classification, setClassification] = useGroupFilter();
  const [sort, setSort] = useState("discovered");
  const scans = useQuery({
    queryKey: ["scans"],
    queryFn: () => api<Page<Scan>>("/scans?limit=100"),
  });
  const groups = useQuery({
    queryKey: ["groups", scanId, offset, classification, sort, pageSize],
    queryFn: () =>
      groupPage<Page<Group>>(
        `/groups?scan_id=${scanId}&sort=${sort}${classification ? `&classification=${classification}` : ""}`,
        offset,
        pageSize,
      ),
    enabled: !!scanId,
    refetchInterval: 1000,
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">Less guesswork, more control</div>
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
              {new Date(scan.created_at).toLocaleString()} ·{" "}
              {displayLabel(scan.status)}
            </option>
          ))}
        </select>
      </div>
      <div className="notice">
        <ShieldCheck size={18} />
        <p>
          Exact copies and approximate media matches are labeled separately.
          Similar groups start with no files selected for deletion. A file may
          appear in both an exact and a similar group. Copy-name recommendations
          are advisory. RAW originals, protected folders, and potential
          photo/video companions stay protected.
        </p>
      </div>
      <GroupFilters
        classification={classification}
        sort={sort}
        onChange={(value, order) => {
          setClassification(value);
          setSort(order);
          setOffset(0);
        }}
      />
      {scanId && (
        <BatchCleanup
          scanId={scanId}
          onPlan={onPlan}
          classification={classification}
        />
      )}
      {!scanId ? (
        <Empty title="Choose a scan to review">
          <button onClick={() => navigate("Scanner")}>
            Go to scanner <ArrowRight size={14} />
          </button>
        </Empty>
      ) : groups.isPending ? (
        <Loading />
      ) : !groups.data?.items.length ? (
        <Empty title="No matching groups">
          Try another filter or choose another scan.
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
        size={pageSize}
        onSizeChange={(size) => {
          setPageSize(size);
          setOffset(0);
        }}
        onChange={setOffset}
      />
    </>
  );
}
export function GroupCard({
  group,
  onPlan,
  thumbnailFirst = false,
  selectForDeletion = true,
  live = false,
}: {
  group: Group;
  onPlan: (plan: Cleanup) => void;
  thumbnailFirst?: boolean;
  selectForDeletion?: boolean;
  live?: boolean;
}) {
  const openPreview = useContext(PreviewContext);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [destination] = useCleanupDestination();
  const client = useQueryClient();
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
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["selection-summary"] });
      return client.invalidateQueries({ queryKey: ["group", group.id] });
    },
  });
  const selectAll = useMutation({
    mutationFn: () => api(`/groups/${group.id}/review`, { keep_ids: [] }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["selection-summary"] });
      return client.invalidateQueries({ queryKey: ["group", group.id] });
    },
  });
  const eligible =
    detail.data?.files.filter(
      (file) => !file.keep && file.status === "ready",
    ) ?? [];
  const selectedCount = detail.data?.selected_count ?? eligible.length;
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
          scanId={group.scan_id}
          onClose={() => setPreviewId(null)}
        />
      )}
      <div className="group-summary">
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
                ? "Exact duplicate"
                : "Similar media · review required"}
            </span>
          </div>
          <strong>{bytes(group.recoverable)} potential</strong>
        </div>
        <p className="hint group-identifier">Group {group.id}</p>
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
                {group.evidence.sample_count} time-spaced visual samples match
                for each pair. Maximum duration difference:{" "}
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
      </div>
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
                onOpen={() =>
                  openPreview
                    ? openPreview(group.id, file.id, group.scan_id)
                    : setPreviewId(file.id)
                }
              />
              <div className="media-details">
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
                  <p className="muted">{displayLabel(file.status)}</p>
                )}
                {file.warnings.map((warning) => (
                  <p className="hint" key={warning}>
                    {warning}
                  </p>
                ))}
              </div>
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
      <div className="group-actionbar">
        <div className="group-actions-heading">
          <strong>Available actions</strong>
          {detail.data?.review_status === "reviewed" && (
            <span className="group-review-state">Selections saved</span>
          )}
        </div>
        <div className="group-actions">
          {detail.data?.files.some((file) => file.media_type === "video") && (
            <VideoCompare groupId={group.id} scanId={group.scan_id} />
          )}
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
          <button
            className="primary"
            disabled={
              !selectedCount ||
              plan.isPending ||
              review.isPending ||
              selectAll.isPending
            }
            onClick={() => plan.mutate()}
          >
            {selectForDeletion ? "Delete selected" : "Delete unchecked"} ·{" "}
            {selectedCount} in this group <ArrowRight size={15} />
          </button>
        </div>
        <details className="group-selection-help">
          <summary>Selection rules & cleanup details</summary>
          <p className="hint">
            {selectForDeletion
              ? "Select the unwanted files, then click Delete selected for this group. Unselected files are kept."
              : "Check the files to keep. Uncheck unwanted files, then preview deletion for this group."}{" "}
            The preview includes selected files across all pages of this group.
            You must confirm before anything is moved.
          </p>
          {group.classification === "EXACT_DUPLICATE" && (
            <p className="hint">
              Keep at least one file, or explicitly choose Select all for
              deletion to keep none. To change the keeper, keep another copy
              first.
            </p>
          )}
        </details>
      </div>
      <ErrorMessage
        error={detail.error || review.error || selectAll.error || plan.error}
      />
    </article>
  );
}
