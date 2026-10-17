import { GroupFilters, type GroupFilter } from "./GroupFilters";
import { BatchCleanup } from "./BatchCleanup";
import { GroupCard } from "../pages/Review";
import type { Cleanup } from "../types/api";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers3, ShieldCheck, ArrowRight } from "lucide-react";
import { api } from "../services/api";
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
  const [classification, setClassification] = useState<GroupFilter>("");
  const [sort, setSort] = useState("discovered");
  const running = ["queued", "running"].includes(status);
  const matches = useQuery({
    queryKey: ["scan-matches", scanId, offset, classification, sort, pageSize],
    queryFn: () =>
      api<Matches>(
        `/scans/${scanId}/matches?offset=${offset}&limit=${pageSize}&sort=${sort}${classification ? `&classification=${classification}` : ""}`,
      ),
    refetchInterval: running ? 1000 : false,
  });
  useEffect(() => {
    if (status === "completed") void matches.refetch();
  }, [status, scanId]);
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
            Matches can grow as scanning continues. Select unwanted files and
            delete per group now or after the scan finishes. Every cleanup
            requires a preview and confirmation.
          </p>
        </div>
      )}
      <GroupFilters
        classification={classification}
        sort={sort}
        pageSize={pageSize}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setOffset(0);
        }}
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
      {matches.data?.items.length ? (
        matches.data.items.map((group) =>
          onPlan ? (
            <GroupCard
              key={group.id}
              group={group}
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
      <ErrorMessage error={matches.error} />
      <Pagination
        offset={offset}
        total={matches.data?.total ?? 0}
        size={pageSize}
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
