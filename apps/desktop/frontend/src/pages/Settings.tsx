import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Download } from "lucide-react";
import { api, prefix } from "../services/api";
import type { Settings as Preferences } from "../types/api";
import { ErrorMessage, Loading } from "../components/ui";
export function Settings() {
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Preferences>("/settings"),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ tools: Record<string, boolean> }>("/health"),
  });
  const [draft, setDraft] = useState<Preferences | null>(null);
  useEffect(() => {
    if (settings.data) setDraft(settings.data);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () => api("/settings", draft, "PUT"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["settings"] }),
  });
  if (!draft)
    return (
      <>
        <Loading />
        <ErrorMessage error={settings.error} />
      </>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">SET UP YOUR Workspace</div>
          <h1>Thoughtful defaults.</h1>
          <p>Local preferences, stored on this computer.</p>
        </div>
      </div>
      <section className="panel">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <label htmlFor="protected">
            Protected directories · one per line
          </label>
          <textarea
            id="protected"
            rows={3}
            value={draft.protected_directories.join("\n")}
            onChange={(e) =>
              setDraft({
                ...draft,
                protected_directories: e.target.value
                  .split("\n")
                  .filter(Boolean),
              })
            }
          />
          <p className="hint">
            Files in these folders can be scanned, but cannot be moved by
            cleanup.
          </p>
          <label htmlFor="excluded-settings">
            Excluded directories · one per line
          </label>
          <textarea
            id="excluded-settings"
            rows={3}
            value={draft.excluded_directories.join("\n")}
            onChange={(e) =>
              setDraft({
                ...draft,
                excluded_directories: e.target.value
                  .split("\n")
                  .filter(Boolean),
              })
            }
          />
          <label htmlFor="excluded-ext">
            Excluded extensions · comma separated
          </label>
          <input
            id="excluded-ext"
            value={draft.excluded_extensions.join(", ")}
            onChange={(e) =>
              setDraft({
                ...draft,
                excluded_extensions: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
          />
          <div className="form-grid">
            <div>
              <label htmlFor="workers">I/O worker concurrency</label>
              <input
                id="workers"
                type="number"
                min={1}
                max={8}
                value={draft.concurrency}
                onChange={(e) =>
                  setDraft({ ...draft, concurrency: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <label htmlFor="theme">Theme</label>
              <select
                id="theme"
                value={draft.theme}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    theme: e.target.value as Preferences["theme"],
                  })
                }
              >
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
          </div>
          <label htmlFor="cleanup-default">Default cleanup destination</label>
          <select
            id="cleanup-default"
            value={draft.cleanup_destination}
            onChange={(event) =>
              setDraft({
                ...draft,
                cleanup_destination: event.target
                  .value as Preferences["cleanup_destination"],
              })
            }
          >
            <option value="trash">OS Trash / Recycle Bin</option>
            <option value="quarantine">Same-volume quarantine</option>
          </select>
          <button className="primary" disabled={save.isPending}>
            <Save size={15} /> Save settings
          </button>
          {save.isSuccess && <p role="status">Settings saved.</p>}
          <ErrorMessage error={save.error} />
        </form>
      </section>
      <section className="panel">
        <h2>Media tools</h2>
        <p className="muted">
          Video similarity uses FFmpeg and FFprobe installed during setup. RAW
          previews use rawpy/LibRaw. ExifTool is optional for additional
          metadata. No tools are downloaded during scanning.
        </p>
        <div className="tool-list">
          {Object.entries(health.data?.tools ?? {}).map(([tool, available]) => (
            <span className="badge" key={tool}>
              {tool} · {available ? "available" : "not installed"}
            </span>
          ))}
        </div>
        <a className="button" href={`${prefix}/diagnostics`} download>
          <Download size={15} /> Export diagnostic log
        </a>
      </section>
    </>
  );
}
