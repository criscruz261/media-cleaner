import { useState } from "react";
import { saveLocal } from "../services/workspace";
import { useQuery } from "@tanstack/react-query";
import { Files, HardDrive, Layers3, ArrowUpRight, Clock3 } from "lucide-react";
import { api, bytes, displayLabel } from "../services/api";
import { Empty, ErrorMessage, Loading } from "../components/ui";
import type { Scan, Page, Cleanup } from "../types/api";
export function Dashboard({
  navigate,
  selectScan,
}: {
  navigate: (page: string) => void;
  selectScan: (id: string) => void;
}) {
  const [cleared, setCleared] = useState<{
    scans: string[];
    cleanup: string[];
  }>(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("media-cleaner.dashboard-cleared") ?? "null",
      );
      return {
        scans: Array.isArray(saved?.scans)
          ? saved.scans.filter((id: unknown) => typeof id === "string")
          : [],
        cleanup: Array.isArray(saved?.cleanup)
          ? saved.cleanup.filter((id: unknown) => typeof id === "string")
          : [],
      };
    } catch {
      return { scans: [], cleanup: [] };
    }
  });
  function saveCleared(value: typeof cleared) {
    setCleared(value);
    saveLocal("media-cleaner.dashboard-cleared", value);
  }
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: () =>
      api<{
        scan_id?: string;
        files: number;
        bytes: number;
        groups: number;
        similar_groups: number;
        recoverable: number;
      }>("/dashboard"),
  });
  const scans = useQuery({
    queryKey: ["scans"],
    queryFn: () => api<Page<Scan>>("/scans?limit=8"),
    refetchInterval: 5000,
  });
  const history = useQuery({
    queryKey: ["cleanup-history"],
    queryFn: () => api<Page<Cleanup>>("/cleanup/history?limit=5"),
  });
  const visibleScans =
    scans.data?.items.filter((scan) => !cleared.scans.includes(scan.id)) ?? [];
  const visibleCleanup =
    history.data?.items.filter((item) => !cleared.cleanup.includes(item.id)) ??
    [];
  const latestHidden =
    !!stats.data?.scan_id && cleared.scans.includes(stats.data.scan_id);
  const summary = latestHidden ? undefined : stats.data;
  const hasCleared = cleared.scans.length > 0 || cleared.cleanup.length > 0;
  return (
    <div className="dashboard-page">
      <div className="page-heading">
        <div>
          <h1>Dashboard</h1>
          <p>Recent scans, matching groups, and cleanup activity.</p>
        </div>
        <div className="actions">
          <button
            disabled={
              !visibleScans.length &&
              !visibleCleanup.length &&
              (!stats.data?.scan_id || latestHidden)
            }
            onClick={() =>
              saveCleared({
                scans: [
                  ...new Set([
                    ...cleared.scans,
                    ...visibleScans.map((scan) => scan.id),
                    ...(stats.data?.scan_id ? [stats.data.scan_id] : []),
                  ]),
                ],
                cleanup: [
                  ...new Set([
                    ...cleared.cleanup,
                    ...visibleCleanup.map((item) => item.id),
                  ]),
                ],
              })
            }
          >
            Clear dashboard view
          </button>
          {hasCleared && (
            <button onClick={() => saveCleared({ scans: [], cleanup: [] })}>
              Restore cleared entries
            </button>
          )}
          <button className="primary" onClick={() => navigate("Scanner")}>
            Start a new scan <ArrowUpRight size={17} />
          </button>
        </div>
      </div>
      <p className="hint">
        Clear dashboard view hides the displayed entries on this browser. Saved
        scans, checkpoints, media files, and recovery records remain available.
      </p>
      {latestHidden && (
        <p className="hint" role="status">
          Latest scan hidden from this dashboard. Restore cleared entries to
          show it again.
        </p>
      )}
      <div className="metrics">
        {[
          [Files, "Files inventoried", summary?.files?.toLocaleString() ?? "—"],
          [HardDrive, "Media size", bytes(summary?.bytes ?? 0)],
          [Layers3, "Exact-match groups", summary?.groups ?? 0],
          [Layers3, "Similar-media groups", summary?.similar_groups ?? 0],
          [
            ArrowUpRight,
            "Exact-copy savings",
            bytes(summary?.recoverable ?? 0),
          ],
        ].map(([Icon, label, value]) => {
          const I = Icon as typeof Files;
          return (
            <article className="metric" key={String(label)}>
              <I size={18} />
              <span>{String(label)}</span>
              <strong>{String(value)}</strong>
            </article>
          );
        })}
      </div>
      <ErrorMessage error={stats.error} />
      <div className="dashboard-history">
        <section className="panel">
          <div className="section-heading">
            <h2>Scan history</h2>
            <span className="muted">Stored on this computer</span>
          </div>
          {scans.isPending ? (
            <Loading />
          ) : visibleScans.length ? (
            <div className="history-list">
              {visibleScans.map((scan) => (
                <button
                  className="history-row"
                  key={scan.id}
                  onClick={() => {
                    selectScan(scan.id);
                    navigate("Review");
                  }}
                >
                  <div className="row-icon">
                    <HardDrive size={19} />
                  </div>
                  <div className="grow">
                    <strong>{scan.options.roots.join(", ")}</strong>
                    <small>
                      {new Date(scan.created_at).toLocaleString()} ·{" "}
                      {scan.discovered.toLocaleString()} files ·{" "}
                      {scan.cache_hits} cached
                    </small>
                  </div>
                  <span className={`badge ${scan.status}`}>
                    {displayLabel(scan.status)}
                  </span>
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          ) : (
            <Empty
              title={
                hasCleared
                  ? "Dashboard scan history cleared"
                  : "Your first scan starts here"
              }
            >
              {hasCleared
                ? "Restore cleared entries above to show your saved scans here."
                : "Choose folders from your computer or a mounted drive."}
            </Empty>
          )}
          <ErrorMessage error={scans.error} />
        </section>
        <section className="panel">
          <div className="section-heading">
            <h2>Recent cleanup</h2>
            <button className="text-button" onClick={() => navigate("Cleanup")}>
              View history <ArrowUpRight size={14} />
            </button>
          </div>
          {visibleCleanup.length ? (
            visibleCleanup.map((item) => (
              <div className="history-row" key={item.id}>
                <Clock3 size={18} />
                <div className="grow">
                  <strong>
                    {item.items.length} files · {item.destination}
                  </strong>
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                </div>
                <span className="badge">{displayLabel(item.status)}</span>
              </div>
            ))
          ) : (
            <p className="muted">
              Cleanup actions and recovery information will appear here.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
