import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Play, Pause, Square, ArrowRight } from "lucide-react";
import { api, bytes } from "../services/api";
import { useScanProgress } from "../hooks/useScanProgress";
import { ErrorMessage } from "../components/ui";
import type { Scan } from "../types/api";
export function Scanner({
  scanId,
  selectScan,
  navigate,
}: {
  scanId: string;
  selectScan: (id: string) => void;
  navigate: (page: string) => void;
}) {
  const [roots, setRoots] = useState(""),
    [excluded, setExcluded] = useState(""),
    [extensions, setExtensions] = useState(""),
    [hidden, setHidden] = useState(false),
    [mode, setMode] = useState("exact");
  const client = useQueryClient();
  const scan = useQuery({
    queryKey: ["scan", scanId],
    queryFn: () => api<Scan>(`/scans/${scanId}`),
    enabled: !!scanId,
    refetchInterval: 2000,
  });
  useScanProgress(scan.data);
  const start = useMutation({
    mutationFn: () =>
      api<Scan>("/scans", {
        roots: roots
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        excluded_directories: excluded.split("\n").filter(Boolean),
        excluded_extensions: extensions
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        include_hidden: hidden,
        mode,
      }),
    onSuccess: (scan) => {
      selectScan(scan.id);
      client.invalidateQueries();
    },
  });
  const control = useMutation({
    mutationFn: (action: string) => api(`/scans/${scanId}/${action}`, {}),
    onSuccess: () => client.invalidateQueries(),
  });
  const browse = useMutation({
    mutationFn: () => api<{ path: string | null }>("/folders/choose", {}),
    onSuccess: (value) => {
      if (value.path)
        setRoots((current) =>
          current ? current + "\n" + value.path : value.path!,
        );
    },
  });
  const active = ["queued", "running"].includes(scan.data?.status ?? "");
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">SCAN YOUR WAY</div>
          <h1>Start with a folder.</h1>
          <p>Internal storage, external drives, or mounted network folders.</p>
        </div>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>
            <FolderOpen size={20} /> Scan locations
          </h2>
          <span className="badge">Read-only analysis</span>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            start.mutate();
          }}
        >
          <div className="section-heading">
            <label htmlFor="roots">Folder paths · one per line</label>
            <button
              type="button"
              disabled={browse.isPending}
              onClick={() => browse.mutate()}
            >
              <FolderOpen size={14} />
              {browse.isPending ? "Choosing…" : "Browse folder"}
            </button>
          </div>
          <ErrorMessage error={browse.error} />
          <textarea
            id="roots"
            required
            rows={3}
            placeholder={"/Volumes/Photos/2025 - Bangkok\n/Users/you/Pictures"}
            value={roots}
            onChange={(e) => setRoots(e.target.value)}
          />
          <p className="hint">
            Use absolute paths or ~. Subfolders are included. Mount or connect
            drives before scanning.
          </p>
          <div className="form-grid">
            <div>
              <label htmlFor="scan-mode">Scan mode</label>
              <select
                id="scan-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="exact">Exact duplicates · all media</option>
                <option value="images">Images · exact duplicates</option>
                <option value="videos">Videos · exact duplicates</option>
              </select>
            </div>
            <div>
              <label htmlFor="extensions">Exclude extensions</label>
              <input
                id="extensions"
                placeholder=".lrv, .insv"
                value={extensions}
                onChange={(e) => setExtensions(e.target.value)}
              />
            </div>
          </div>
          <label htmlFor="excluded">
            Excluded folders · one absolute path per line
          </label>
          <textarea
            id="excluded"
            rows={2}
            value={excluded}
            onChange={(e) => setExcluded(e.target.value)}
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={hidden}
              onChange={(e) => setHidden(e.target.checked)}
            />{" "}
            Include hidden files and folders
          </label>
          <div className="form-footer">
            <p className="muted">
              SHA-256 verifies complete file contents. No media is uploaded.
            </p>
            <button className="primary" disabled={active || start.isPending}>
              Start scan <ArrowRight size={16} />
            </button>
          </div>
          <ErrorMessage error={start.error} />
        </form>
      </section>
      {scan.data && (
        <section className="panel">
          <div className="section-heading">
            <h2>Current scan</h2>
            <span className="badge">{scan.data.status}</span>
          </div>
          <p>{scan.data.stage.replaceAll("_", " ")}</p>
          <progress
            max={Math.max(scan.data.discovered, 1)}
            value={scan.data.processed}
          />
          <div className="progress-stats">
            <span>{scan.data.discovered} discovered</span>
            <span>{scan.data.processed} processed</span>
            <span>{bytes(scan.data.bytes_processed)} processed</span>
            <span>{scan.data.cache_hits} cached</span>
            <span>{scan.data.errors} errors</span>
          </div>
          <div className="actions">
            {active ? (
              <>
                <button
                  disabled={control.isPending}
                  onClick={() => control.mutate("pause")}
                >
                  <Pause size={15} /> Pause
                </button>
                <button
                  disabled={control.isPending}
                  onClick={() => control.mutate("cancel")}
                >
                  <Square size={14} /> Cancel
                </button>
              </>
            ) : ["paused", "interrupted", "failed"].includes(
                scan.data.status,
              ) ? (
              <>
                <button
                  disabled={control.isPending}
                  onClick={() => control.mutate("resume")}
                >
                  <Play size={15} /> Resume
                </button>
                <button onClick={() => control.mutate("cancel")}>Cancel</button>
              </>
            ) : null}
            <button onClick={() => navigate("Review")}>
              Review matches <ArrowRight size={15} />
            </button>
          </div>
          <ErrorMessage error={control.error} />
          <ErrorMessage error={scan.data.error} />
        </section>
      )}
    </>
  );
}
