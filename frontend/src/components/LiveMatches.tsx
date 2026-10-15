import { VideoCompare } from "./VideoCompare";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers3, ShieldCheck, ArrowRight } from "lucide-react";
import { api, bytes } from "../services/api";
import type { Group, Page, MediaFile } from "../types/api";
import { ErrorMessage, Pagination } from "./ui";
import { MediaPreview } from "./MediaPreview";
type Matches = Page<Group> & {
  exact_groups: number;
  similar_groups: number;
  provisional: boolean;
};
export function LiveMatches({
  scanId,
  status,
  navigate,
}: {
  scanId: string;
  status: string;
  navigate: (page: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const running = ["queued", "running"].includes(status);
  const matches = useQuery({
    queryKey: ["scan-matches", scanId, offset],
    queryFn: () =>
      api<Matches>(`/scans/${scanId}/matches?offset=${offset}&limit=6`),
    refetchInterval: running ? 1000 : false,
  });
  return (
    <section className="panel" aria-label="Live matches">
      <div className="section-heading">
        <h2>
          <Layers3 size={19} /> Matches found so far
        </h2>
        <span className="badge">
          {running
            ? "Live updates"
            : status === "completed"
              ? "Final results"
              : "Saved results"}
        </span>
      </div>
      <div className="progress-stats" aria-live="polite">
        <strong>{matches.data?.exact_groups ?? 0} exact groups</strong>
        <strong>{matches.data?.similar_groups ?? 0} similar groups</strong>
      </div>
      {status !== "completed" && (
        <div className="notice">
          <ShieldCheck size={18} />
          <p>
            These results are provisional and can grow as scanning continues.
            Review selections and cleanup become available when the scan
            finishes.
          </p>
        </div>
      )}
      {matches.data?.items.length ? (
        matches.data.items.map((group) => (
          <LiveMatch key={group.id} group={group} running={running} />
        ))
      ) : (
        <p className="muted">
          {running
            ? "Matches will appear here as soon as files are compared."
            : "No matching groups saved for this scan."}
        </p>
      )}
      <ErrorMessage error={matches.error} />
      <Pagination
        offset={offset}
        total={matches.data?.total ?? 0}
        size={6}
        onChange={setOffset}
      />
      {status === "completed" && (
        <button className="primary" onClick={() => navigate("Review")}>
          Choose which files to keep <ArrowRight size={15} />
        </button>
      )}
    </section>
  );
}
function LiveMatch({ group, running }: { group: Group; running: boolean }) {
  const detail = useQuery({
    queryKey: ["scanner-match", group.id],
    queryFn: () =>
      api<Group & { files: MediaFile[] }>(`/groups/${group.id}?limit=3`),
    refetchInterval: running ? 1000 : false,
  });
  const kind =
    group.classification === "EXACT_DUPLICATE"
      ? "Exact copies"
      : group.evidence.media_kind === "sequence"
        ? "Similar videos / animations"
        : "Similar photos";
  return (
    <article className="live-match">
      <div className="section-heading">
        <h3>
          {kind} · {group.member_count} files
        </h3>
        <span className="badge">
          {group.classification === "EXACT_DUPLICATE"
            ? "SHA-256 verified"
            : "Manual review required"}
        </span>
      </div>
      {detail.data?.files.some((file) => file.media_type === "video") && (
        <VideoCompare groupId={group.id} />
      )}
      <div className="media-grid">
        {detail.data?.files.map((file) => (
          <div className="media-card" key={file.id}>
            <MediaPreview file={file} />
            <strong className="filename">{file.name}</strong>
            <p className="file-path">{file.path}</p>
            <span className="muted">{bytes(file.size)}</span>
          </div>
        ))}
      </div>
      {group.member_count > 3 && (
        <p className="hint">
          Showing 3 of {group.member_count} files. All members are available in
          Duplicate review after scanning.
        </p>
      )}
      <ErrorMessage error={detail.error} />
    </article>
  );
}
