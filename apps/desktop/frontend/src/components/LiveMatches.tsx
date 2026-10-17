import { groupPage } from "../services/groupPages";
import { GroupFilters, useGroupFilter } from "./GroupFilters";
import { BatchCleanup } from "./BatchCleanup";
import { GroupCard } from "../pages/Review";
import type { Cleanup } from "../types/api";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers3, ShieldCheck, ArrowRight } from "lucide-react";
import type { Group, Page } from "../types/api";
import { ErrorMessage, Pagination } from "./ui";
type Matches = Page<Group> & {
  exact_groups: number;
  similar_groups: number;
  provisional: boolean;
};
export function LiveMatches({
  scanId,
  status,
  navigate,
  onPlan,
}: {
  scanId: string;
  status: string;
  navigate: (page: string) => void;
  onPlan?: (plan: Cleanup) => void;
}) {
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [classification, setClassification] = useGroupFilter();
  const [sort, setSort] = useState("discovered");
  const running = ["queued", "running"].includes(status);
  const matches = useQuery({
    queryKey: ["scan-matches", scanId, offset, classification, sort, pageSize],
    queryFn: () =>
      groupPage<Matches>(
        `/scans/${scanId}/matches?sort=${sort}${classification ? `&classification=${classification}` : ""}`,
        offset,
        pageSize,
      ),
    refetchInterval: running ? 1000 : false,
  });
  useEffect(() => {
    if (status === "completed") void matches.refetch();
  }, [status, scanId]);
  return (
    <section className="panel live-matches" aria-label="Live matches">
      <div className="live-matches-controls">
        <div className="section-heading">
          <h2>
            <Layers3 size={19} /> Matches found so far
          </h2>
          <div className="progress-stats" aria-live="polite">
            <strong>{matches.data?.exact_groups ?? 0} exact groups</strong>
            <strong>{matches.data?.similar_groups ?? 0} similar groups</strong>
          </div>
          <span className="badge">
            {running
              ? "Live updates"
              : status === "completed"
                ? "Final results"
                : "Saved results"}
          </span>
        </div>
        {status !== "completed" && (
          <div className="notice">
            <ShieldCheck size={18} />
            <p>
              Groups may update while scanning. Every deletion requires review
              and confirmation.
            </p>
          </div>
        )}
        <GroupFilters
          classification={classification}
          sort={sort}
          onChange={(value, order) => {
            setClassification(value);
            setSort(order);
            setOffset(0);
          }}
        />
        {onPlan && (
          <BatchCleanup
            scanId={scanId}
            onPlan={onPlan}
            classification={classification}
          />
        )}
      </div>
      <div className="live-matches-results">
        {matches.data?.items.length ? (
          matches.data.items.map((group, index) =>
            onPlan ? (
              <GroupCard
                key={group.id}
                group={group}
                position={offset + index + 1}
                totalGroups={matches.data.total}
                onPlan={onPlan}
                thumbnailFirst
                selectForDeletion
                live={running}
              />
            ) : (
              <button key={group.id} onClick={() => navigate("Review")}>
                Select and delete files in this group
              </button>
            ),
          )
        ) : (
          <p className="muted">
            {running
              ? "Matches will appear here as soon as files are compared."
              : "No matching groups saved for this scan."}
          </p>
        )}
      </div>
      <ErrorMessage error={matches.error} />
      <Pagination
        offset={offset}
        total={matches.data?.total ?? 0}
        size={pageSize}
        onSizeChange={(size) => {
          setPageSize(size);
          setOffset(0);
        }}
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
