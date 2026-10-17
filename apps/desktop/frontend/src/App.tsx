import { CleanupDialog } from "./components/CleanupDialog";
import { ShutdownControl } from "./components/ShutdownDialog";
import { GroupPreview, PreviewContext } from "./components/GroupPreview";
import { ScanProgress } from "./components/ScanProgress";
import { useEffect, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  ScanLine,
  Layers3,
  ShieldCheck,
  Settings as SettingsIcon,
  Leaf,
  LockKeyhole,
  ArrowUpRight,
} from "lucide-react";
import { Dashboard } from "./pages/Dashboard";
import { Scanner } from "./pages/Scanner";
import { Review } from "./pages/Review";
import { Cleanup } from "./pages/Cleanup";
import { Settings } from "./pages/Settings";
import { ErrorMessage } from "./components/ui";
import { loadWorkspace, saveLocal, workspaceKey } from "./services/workspace";
import type { Scan } from "./types/api";
import { api, prefix } from "./services/api";
import type {
  Cleanup as CleanupPlan,
  Settings as Preferences,
} from "./types/api";
const pages = [
  ["Dashboard", LayoutDashboard],
  ["Scanner", ScanLine],
  ["Review", Layers3],
  ["Cleanup", ShieldCheck],
  ["Settings", SettingsIcon],
] as const;
export function App() {
  const [stopped, setStopped] = useState(false);
  const [preview, setPreview] = useState<{
    groupId: string;
    initialId: string;
    scanId: string;
  } | null>(null);
  const [sidebar, setSidebar] = useState(() => {
    try {
      const value = JSON.parse(
        localStorage.getItem("media-cleaner.sidebar") ?? "null",
      );
      return {
        width: Math.min(420, Math.max(200, Number(value?.width) || 244)),
        collapsed: value?.collapsed === true,
      };
    } catch {
      return { width: 244, collapsed: false };
    }
  });
  useEffect(() => {
    saveLocal("media-cleaner.sidebar", sidebar);
  }, [sidebar]);
  const [saved] = useState(loadWorkspace);
  const [connected, setConnected] = useState(false),
    [token, setToken] = useState(""),
    [error, setError] = useState<unknown>(null),
    [page, setPage] = useState(saved.page),
    [scanId, setScanId] = useState(saved.scanId),
    [plan, setPlan] = useState<CleanupPlan | null>(null);
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Preferences>("/settings"),
    enabled: connected,
  });
  useEffect(() => {
    saveLocal(workspaceKey, { page, scanId });
  }, [page, scanId]);
  useEffect(() => {
    if (!connected) return;
    let cancelled = false;
    async function recover() {
      try {
        const active = await api<{ scan: Scan | null }>("/scans/active");
        if (cancelled) return;
        if (
          active.scan &&
          (!scanId ||
            (page === "Scanner" &&
              ["queued", "running"].includes(active.scan.status)))
        ) {
          setScanId(active.scan.id);
          setPage("Scanner");
          return;
        }
        if (scanId) {
          try {
            await api(`/scans/${scanId}`);
          } catch {
            if (!cancelled) {
              setScanId(active.scan?.id ?? "");
              setPage(active.scan ? "Scanner" : "Dashboard");
            }
          }
        }
      } catch {
        /* Keep the saved scan selected during a temporary backend outage. */
      }
    }
    void recover();
    return () => {
      cancelled = true;
    };
  }, [connected]);
  async function connect(value: string) {
    try {
      const response = await fetch(prefix + "/session", {
        method: "POST",
        headers: { Authorization: `Bearer ${value}` },
      });
      if (!response.ok)
        throw new Error(
          "Invalid launch token. Copy the token printed by run.sh.",
        );
      setConnected(true);
      setError(null);
      setToken("");
    } catch (error) {
      setError(error);
    }
  }
  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const launchToken = fragment.get("token");
    if (launchToken) {
      window.history.replaceState(null, "", window.location.pathname);
      void connect(launchToken);
    } else {
      api("/health")
        .then(() => setConnected(true))
        .catch(() => {});
    }
  }, []);
  useEffect(() => {
    const theme = settings.data?.theme ?? "system";
    document.documentElement.dataset.theme = theme;
  }, [settings.data?.theme]);
  if (stopped)
    return (
      <main className="connect-screen">
        <div className="connect-card">
          <h1>App safely stopped</h1>
          <p>
            Your checkpoint and selections are saved. You can close this tab.
          </p>
          <p>
            Run ./run.sh to reopen the app, then choose Resume from checkpoint.
          </p>
        </div>
      </main>
    );
  if (!connected)
    return (
      <main className="connect-screen">
        <div className="connect-card">
          <Leaf size={38} />
          <div className="eyebrow">LOCAL BY DEFAULT</div>
          <h1>Media Cleaner</h1>
          <p>
            Connect to your local library workspace using the launch link or
            token printed in your terminal.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void connect(token);
            }}
          >
            <label htmlFor="token">Local launch token</label>
            <input
              type="password"
              id="token"
              autoComplete="off"
              required
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <button className="primary">
              Connect securely <ArrowUpRight size={16} />
            </button>
          </form>
          <ErrorMessage error={error} />
        </div>
      </main>
    );
  return (
    <PreviewContext.Provider
      value={(groupId, initialId, scanId) =>
        setPreview({ groupId, initialId, scanId })
      }
    >
      <div
        className={`app-shell ${sidebar.collapsed ? "sidebar-collapsed" : ""}`}
        style={
          {
            "--sidebar-width": `${sidebar.collapsed ? 76 : sidebar.width}px`,
          } as CSSProperties
        }
      >
        <aside className="sidebar">
          <button
            className="sidebar-toggle"
            aria-label={
              sidebar.collapsed ? "Expand sidebar" : "Collapse sidebar"
            }
            aria-expanded={!sidebar.collapsed}
            onClick={() =>
              setSidebar((value) => ({ ...value, collapsed: !value.collapsed }))
            }
          >
            {sidebar.collapsed ? "»" : "«"}
          </button>
          <div
            className="sidebar-resizer"
            role="separator"
            aria-label="Resize sidebar"
            aria-orientation="vertical"
            aria-valuemin={200}
            aria-valuemax={420}
            aria-valuenow={sidebar.width}
            tabIndex={sidebar.collapsed ? -1 : 0}
            onPointerDown={(event) => {
              if (!sidebar.collapsed)
                event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                setSidebar({
                  collapsed: false,
                  width: Math.min(420, Math.max(200, event.clientX)),
                });
            }}
            onPointerUp={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onKeyDown={(event) => {
              if (
                ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
              ) {
                event.preventDefault();
                setSidebar((value) => ({
                  ...value,
                  width:
                    event.key === "Home"
                      ? 200
                      : event.key === "End"
                        ? 420
                        : Math.min(
                            420,
                            Math.max(
                              200,
                              value.width +
                                (event.key === "ArrowRight" ? 16 : -16),
                            ),
                          ),
                }));
              }
            }}
          />
          <a
            className="brand"
            href="#"
            onClick={(e) => {
              e.preventDefault();
              setPage("Dashboard");
            }}
          >
            <span className="brand-icon">
              <Leaf size={23} />
            </span>
            <span>
              Media Cleaner<small>A LITTLE LESS CLUTTER</small>
            </span>
          </a>
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {pages.map(([name, Icon]) => (
              <button
                key={name}
                aria-label={name === "Review" ? "Duplicate review" : name}
                title={name === "Review" ? "Duplicate review" : name}
                className={page === name ? "active" : ""}
                onClick={() => setPage(name)}
                aria-current={page === name ? "page" : undefined}
              >
                <Icon size={19} />
                <span className="nav-text">
                  {name === "Review" ? "Duplicate review" : name}
                </span>
              </button>
            ))}
          </nav>
          <div className="sidebar-note">
            <LockKeyhole size={20} />
            <strong>Your media stays yours.</strong>
            <p>
              Local analysis. No uploads.
              <br />
              No account required.
            </p>
            <span>
              <i /> Running on this computer
            </span>
          </div>
          <div className="sidebar-footer">
            PHASE 3 <span>v0.1.0</span>
          </div>
        </aside>
        <div className="workspace">
          <header>
            <div>
              <span className="muted">Workspace</span>
              <span className="breadcrumb">/</span>
              {page === "Review" ? "Duplicate review" : page}
            </div>
            <ShutdownControl
              onStopped={() => {
                setPreview(null);
                setPlan(null);
                setConnected(false);
                setStopped(true);
              }}
            />
            <span className="local-badge">
              <span /> Local & private
            </span>
          </header>
          <div className="sticky-review-progress">
            <ScanProgress scanId={scanId} />
          </div>
          <main className="content">
            {page === "Dashboard" ? (
              <Dashboard navigate={setPage} selectScan={setScanId} />
            ) : page === "Scanner" ? (
              <Scanner
                onPlan={(value) => {
                  setPlan(value);
                }}
                scanId={scanId}
                selectScan={setScanId}
                navigate={setPage}
              />
            ) : page === "Review" ? (
              <Review
                scanId={scanId}
                selectScan={setScanId}
                navigate={setPage}
                onPlan={(value) => {
                  setPlan(value);
                }}
              />
            ) : page === "Cleanup" ? (
              <Cleanup plan={null} onComplete={() => {}} />
            ) : (
              <Settings />
            )}
            <footer>
              <span>
                Built for your memories. Designed for your peace of mind.
              </span>
              <span>
                <ShieldCheck size={13} /> Analysis never changes your originals.
              </span>
            </footer>
          </main>
        </div>
      </div>
      {preview && (
        <GroupPreview {...preview} onClose={() => setPreview(null)} />
      )}
      {plan && (
        <CleanupDialog
          key={plan.id}
          plan={plan}
          onClose={() => setPlan(null)}
        />
      )}
    </PreviewContext.Provider>
  );
}
