import { useEffect, useState } from "react";
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
    <div className="app-shell">
      <aside className="sidebar">
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
              className={page === name ? "active" : ""}
              onClick={() => setPage(name)}
              aria-current={page === name ? "page" : undefined}
            >
              <Icon size={19} />
              {name === "Review" ? "Duplicate review" : name}
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
          <span className="local-badge">
            <span /> Local & private
          </span>
        </header>
        <main className="content">
          {page === "Dashboard" ? (
            <Dashboard navigate={setPage} selectScan={setScanId} />
          ) : page === "Scanner" ? (
            <Scanner
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
                setPage("Cleanup");
              }}
            />
          ) : page === "Cleanup" ? (
            <Cleanup plan={plan} onComplete={() => setPlan(null)} />
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
  );
}
