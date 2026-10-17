import { ActivityThumbnails } from "../components/ActivityThumbnails";
import { ScannerResetContext } from "../components/ScannerResetContext";
import { ScanWorkflow } from "../components/ScanWorkflow";
import { useState, useEffect, useContext } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  useIsMutating,
} from "@tanstack/react-query";
import {
  LoaderCircle,
  FolderOpen,
  Play,
  Pause,
  Square,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { api, bytes } from "../services/api";
import { useScanProgress } from "../hooks/useScanProgress";
import { LiveMatches } from "../components/LiveMatches";
import { loadDraft, saveLocal, draftKey } from "../services/workspace";
import { ErrorMessage, Pagination } from "../components/ui";
import type { Scan, Page, Cleanup } from "../types/api";
export function Scanner({
  scanId,
  selectScan,
  navigate,
  onPlan,
}: {
  scanId: string;
  selectScan: (id: string) => void;
  navigate: (page: string) => void;
  onPlan?: (plan: Cleanup) => void;
}) {
  const resetWorkspace = useContext(ScannerResetContext);
  const busy = useIsMutating() > 0;
  const resetScanner = () => {
    setWarningOffset(0);
    if (resetWorkspace) resetWorkspace();
    else {
      selectScan("");
      navigate("Scanner");
    }
  };
  const [showThumbnails, setShowThumbnails] = useState(() => {
    try {
      return localStorage.getItem("media-cleaner.scan-thumbnails") !== "false";
    } catch {
      return true;
    }
  });
  useEffect(
    () => saveLocal("media-cleaner.scan-thumbnails", showThumbnails),
    [showThumbnails],
  );
  const [draft] = useState(loadDraft);
  const [roots, setRoots] = useState(draft.roots),
    [excluded, setExcluded] = useState(draft.excluded),
    [extensions, setExtensions] = useState(draft.extensions),
    [hidden, setHidden] = useState(draft.hidden),
    [mode, setMode] = useState(draft.mode),
    [sensitivity, setSensitivity] = useState(draft.sensitivity),
    [warningOffset, setWarningOffset] = useState(0);
  useEffect(() => {
    saveLocal(draftKey, {
      roots,
      excluded,
      extensions,
      hidden,
      mode,
      sensitivity,
    });
  }, [roots, excluded, extensions, hidden, mode, sensitivity]);
  const client = useQueryClient();
  const scan = useQuery({
    queryKey: ["scan", scanId],
    queryFn: () => api<Scan>(`/scans/${scanId}`),
    enabled: !!scanId,
    refetchInterval: 2000,
  });
  useScanProgress(scan.data);
  const warnings = useQuery({
    queryKey: ["scan-warnings", scanId, warningOffset],
    queryFn: () =>
      api<Page<{ id: string; path: string; warnings: string[] }>>(
        `/scans/${scanId}/warnings?offset=${warningOffset}&limit=20`,
      ),
    enabled:
      !!scanId &&
      !["queued", "running"].includes(scan.data?.status ?? "running"),
  });
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
        sensitivity,
      }),
    onSuccess: (scan) => {
      selectScan(scan.id);
      setWarningOffset(0);
      client.invalidateQueries();
    },
  });
  const control = useMutation({
    mutationFn: (action: string) => api(`/scans/${scanId}/${action}`, {}),
    onSuccess: (_, action) => {
      void client.invalidateQueries();
      if (action === "stop") resetScanner();
    },
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
    <div className="scanner-page">
      <div className="page-heading">
        <div>
          <h1>Scanner</h1>
          <p>Choose folders, scan media, then review matches before cleanup.</p>
        </div>
        <button
          disabled={busy || (!!scanId && !scan.data)}
          onClick={() => {
            if (
              ["queued", "running", "paused", "interrupted"].includes(
                scan.data?.status ?? "",
              )
            )
              control.mutate("stop");
            else resetScanner();
          }}
        >
          {control.isPending && control.variables === "stop"
            ? "Stopping & resetting…"
            : "Reset scanner"}
        </button>
      </div>
      <ScanWorkflow scan={scan.data} />
      <details className="panel scanner-setup" open={!scanId}>
        <summary>
          <FolderOpen size={18} /> Scan setup{" "}
          <span className="hint">
            {roots.split("\n").filter((line) => line.trim()).length} folders ·{" "}
            {mode === "similar" ? "Similar media" : "Exact matches"}
          </span>
        </summary>
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
            rows={2}
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
                <option value="similar">
                  Similar photos, videos & animations
                </option>
                <option value="exact">Exact duplicates · all media</option>
                <option value="images">Images · exact duplicates</option>
                <option value="videos">Videos · exact duplicates</option>
              </select>
            </div>
            {mode === "similar" && (
              <div>
                <label htmlFor="sensitivity">
                  Media similarity sensitivity
                </label>
                <select
                  id="sensitivity"
                  value={sensitivity}
                  onChange={(event) => setSensitivity(event.target.value)}
                >
                  <option value="strict">Strict · fewer, closer matches</option>
                  <option value="balanced">
                    Balanced · re-encoded and lightly edited media
                  </option>
                  <option value="broad">
                    Broad · more candidates to review
                  </option>
                </select>
              </div>
            )}
          </div>
          <details className="scanner-advanced">
            <summary>Advanced options · exclusions & hidden files</summary>
            <p className="hint">
              Photo pHash + dHash and time-spaced video/animation frame
              comparisons. Videos may have different audio. Crops, trims and
              partial clips can be missed. Unsupported decoders are reported
              below the scan.
            </p>
            <div>
              <label htmlFor="extensions">Exclude extensions</label>
              <input
                id="extensions"
                placeholder=".lrv, .insv"
                value={extensions}
                onChange={(e) => setExtensions(e.target.value)}
              />
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
          </details>
          <div className="form-footer">
            <p className="muted">
              All analysis stays local. Similar-media results require manual
              review; exact copies are verified with SHA-256.
            </p>
            <button className="primary" disabled={active || start.isPending}>
              Start scan <ArrowRight size={16} />
            </button>
          </div>
          <ErrorMessage error={start.error} />
        </form>
      </details>
      {scan.data && (
        <>
          <section className="panel">
            <div className="section-heading">
              <h2>Current scan</h2>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={showThumbnails}
                  onChange={(event) => setShowThumbnails(event.target.checked)}
                />
                Show processing thumbnails
              </label>
              <span className="badge">{scan.data.status}</span>
            </div>
            <p>{scan.data.stage.replaceAll("_", " ")}</p>
            {showThumbnails && !!scan.data.activity?.length && (
              <ActivityThumbnails activity={scan.data.activity} />
            )}

            <p className="file-path">{scan.data.options?.roots?.join(" · ")}</p>
            {scan.data.stage === "discovery" ? (
              <>
                <progress aria-label="Discovering media" />
                <p className="hint">
                  Discovering files; the final total is not known yet.
                </p>
              </>
            ) : (
              <>
                <progress
                  aria-label="Saved file progress"
                  max={Math.max(scan.data.discovered, 1)}
                  value={scan.data.processed}
                />
                <p className="hint">
                  {scan.data.processed} of {scan.data.discovered} file
                  checkpoints saved ·{" "}
                  {Math.min(
                    100,
                    Math.round(
                      (scan.data.processed /
                        Math.max(scan.data.discovered, 1)) *
                        100,
                    ),
                  )}
                  %
                </p>
              </>
            )}
            <div className="progress-stats">
              <span>{scan.data.discovered} discovered</span>
              <span>{scan.data.processed} processed</span>
              <span>
                {bytes(scan.data.bytes_processed)} /{" "}
                {bytes(scan.data.total_bytes ?? 0)} saved media
              </span>
              <span>
                {Math.max(0, scan.data.discovered - scan.data.processed)} files
                remaining
              </span>
              <span>{scan.data.cache_hits} cached</span>
              <span>{scan.data.errors} errors</span>
            </div>
            <details className="scanner-activity">
              <summary className="scanner-activity-toggle">
                <span>File activity</span>
                {active ||
                control.isPending ||
                /saving checkpoint|finalizing completed/i.test(
                  scan.data.stage,
                ) ? (
                  <>
                    <LoaderCircle
                      size={15}
                      className="animate-spin"
                      aria-hidden="true"
                    />
                    <span className="scanner-activity-state">
                      {scan.data.activity?.length
                        ? `Processing · ${scan.data.activity.length} files ongoing`
                        : "Working…"}
                    </span>
                  </>
                ) : (
                  <span className="scanner-activity-state">
                    {scan.data.status === "completed"
                      ? "Complete"
                      : scan.data.status === "paused"
                        ? "Paused"
                        : "Stopped"}
                  </span>
                )}
              </summary>
              <div className="scan-activity" aria-label="Current scan activity">
                {scan.data.activity?.map((item) => (
                  <div key={item.path}>
                    <p className="file-path">
                      <strong>{item.phase}</strong> · {item.path}
                    </p>
                    {item.phase === "hashing" ? (
                      <>
                        <progress
                          aria-label={`Reading ${item.path}`}
                          max={Math.max(item.size, 1)}
                          value={item.bytes_done}
                        />
                        <small>
                          {bytes(item.bytes_done)} / {bytes(item.size)}
                        </small>
                      </>
                    ) : item.frames_total ? (
                      <>
                        <progress
                          aria-label={`Comparing ${item.path}`}
                          max={item.frames_total}
                          value={item.frames_done}
                        />
                        <small>
                          {item.frames_done} / {item.frames_total} samples
                        </small>
                      </>
                    ) : (
                      <progress aria-label={`Processing ${item.path}`} />
                    )}
                  </div>
                ))}
              </div>

              {!scan.data.activity?.length && (
                <p className="hint">
                  {active
                    ? "Waiting for the next file activity update…"
                    : "No files are being processed."}
                </p>
              )}
              <div className="scanner-recovery">
                <strong>
                  <ShieldCheck size={14} /> Checkpoint & recovery
                </strong>
                {scan.data.checkpoint_storage && (
                  <dl className="checkpoint-locations">
                    <dt>Scan checkpoint database</dt>
                    <dd>
                      <code>{scan.data.checkpoint_storage.database}</code>
                    </dd>
                    <dt>Recovery cache folders</dt>
                    {scan.data.checkpoint_storage.folder_caches.map((path) => (
                      <dd key={path}>
                        <code>{path}</code>
                      </dd>
                    ))}
                  </dl>
                )}
                <p className="hint">
                  Each folder cache stores per-file JSON checkpoints in
                  subfolders. The database stores scan progress and review
                  history; cache write failures are listed in scan warnings.
                </p>

                <p>
                  Saved automatically after each file
                  {scan.data.checkpoint_at
                    ? ` · Last checkpoint ${new Date(scan.data.checkpoint_at).toLocaleTimeString()}`
                    : ""}
                  . Completed-file analysis and selections are also saved in
                  .media-cleaner-cache inside each selected folder. Refreshing
                  this page does not stop the scan. After a backend restart,
                  choose Resume; an unfinished file starts again safely.
                </p>
              </div>
            </details>
            <div className="actions">
              {active ? (
                <>
                  <button
                    disabled={control.isPending}
                    onClick={() => control.mutate("checkpoint")}
                  >
                    <Pause size={15} /> Pause
                  </button>
                  <button
                    disabled={control.isPending}
                    onClick={() => control.mutate("stop")}
                  >
                    <Square size={14} /> Stop scan
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
                  <button onClick={() => control.mutate("stop")}>
                    Stop scan
                  </button>
                </>
              ) : null}
              <button
                disabled={!scan.data.discovered}
                onClick={() => navigate("Review")}
              >
                Review matches <ArrowRight size={15} />
              </button>
            </div>
            <ErrorMessage error={control.error} />
            <ErrorMessage error={scan.data.error} />
            {!!warnings.data?.total && (
              <details>
                <summary>
                  {warnings.data.total} files have warnings or skipped
                  comparisons
                </summary>
                {warnings.data.items.map((file) => (
                  <div className="operation-item" key={file.id}>
                    <strong>{file.path}</strong>
                    {file.warnings.map((warning, index) => (
                      <p key={index}>{warning}</p>
                    ))}
                  </div>
                ))}
                <Pagination
                  offset={warningOffset}
                  total={warnings.data.total}
                  size={20}
                  onChange={setWarningOffset}
                />
              </details>
            )}
            <ErrorMessage error={warnings.error} />
          </section>
          <LiveMatches
            onPlan={onPlan}
            key={scanId}
            scanId={scanId}
            status={scan.data.status}
            navigate={navigate}
          />
        </>
      )}
    </div>
  );
}
