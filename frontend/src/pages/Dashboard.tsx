import { useQuery } from "@tanstack/react-query";
import { Files, HardDrive, Layers3, ArrowUpRight, Clock3 } from "lucide-react";
import { api, bytes } from "../services/api";
import { Empty, ErrorMessage, Loading } from "../components/ui";
import type { Scan, Page, Cleanup } from "../types/api";
export function Dashboard({
  navigate,
  selectScan,
}: {
  navigate: (page: string) => void;
  selectScan: (id: string) => void;
}) {
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: () =>
      api<{
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
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR LIBRARY, LIGHTER</div>
          <h1>
            A little space.
            <br />
            <span>A lot more clarity.</span>
          </h1>
          <p>Find repeated media. Keep the memories that matter.</p>
        </div>
        <button className="primary" onClick={() => navigate("Scanner")}>
          Start a new scan <ArrowUpRight size={17} />
        </button>
      </div>
      <div className="metrics">
        {[
          [
            Files,
            "Files inventoried",
            stats.data?.files?.toLocaleString() ?? "—",
          ],
          [HardDrive, "Media size", bytes(stats.data?.bytes ?? 0)],
          [Layers3, "Exact-match groups", stats.data?.groups ?? 0],
          [Layers3, "Similar-media groups", stats.data?.similar_groups ?? 0],
          [
            ArrowUpRight,
            "Exact-copy savings",
            bytes(stats.data?.recoverable ?? 0),
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
      <section className="panel">
        <div className="section-heading">
          <h2>Scan history</h2>
          <span className="muted">Stored on this computer</span>
        </div>
        {scans.isPending ? (
          <Loading />
        ) : scans.data?.items.length ? (
          <div className="history-list">
            {scans.data.items.map((scan) => (
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
                    {scan.discovered.toLocaleString()} files · {scan.cache_hits}{" "}
                    cached
                  </small>
                </div>
                <span className={`badge ${scan.status}`}>{scan.status}</span>
                <ArrowUpRight size={16} />
              </button>
            ))}
          </div>
        ) : (
          <Empty title="Your first scan starts here">
            Choose folders from your computer or a mounted drive.
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
        {history.data?.items.length ? (
          history.data.items.map((item) => (
            <div className="history-row" key={item.id}>
              <Clock3 size={18} />
              <div className="grow">
                <strong>
                  {item.items.length} files · {item.destination}
                </strong>
                <small>{new Date(item.created_at).toLocaleString()}</small>
              </div>
              <span className="badge">{item.status}</span>
            </div>
          ))
        ) : (
          <p className="muted">
            Cleanup actions and recovery information will appear here.
          </p>
        )}
      </section>
    </>
  );
}
