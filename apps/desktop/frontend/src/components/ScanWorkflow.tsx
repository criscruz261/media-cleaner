import type { Scan } from "../types/api";

const steps = [
  "Choose folders",
  "Discover files",
  "Analyze & match",
  "Finalize groups",
  "Review & clean up",
];
export function ScanWorkflow({ scan }: { scan?: Scan }) {
  const stopped =
    !!scan &&
    ["paused", "interrupted", "failed", "cancelled"].includes(scan.status);
  const stage = scan?.stage ?? "";
  const current = !scan
    ? 0
    : scan.status === "completed"
      ? 4
      : stage === "discovery" || scan.status === "queued"
        ? 1
        : stage === "grouping"
          ? 3
          : stopped && !scan.discovered
            ? 1
            : 2;
  const now = !scan
    ? "Choose folders and start a scan."
    : scan.status === "completed"
      ? "Scan complete. Review matches and select files for deletion."
      : stopped
        ? `${scan.status === "paused" ? "Paused" : scan.status === "interrupted" ? "Interrupted" : scan.status === "cancelled" ? "Cancelled" : "Scan failed"} · ${stage.replaceAll("_", " ")}`
        : scan.status === "queued"
          ? "Waiting for scanning to begin."
          : current === 1
            ? "Discovering media in the selected folders."
            : current === 3
              ? "Finalizing match groups and keeper suggestions."
              : `Analyzing media and publishing matches${
                  scan.activity?.length
                    ? ` · ${scan.activity
                        .map((item) => item.phase)
                        .filter(
                          (phase, index, phases) =>
                            phases.indexOf(phase) === index,
                        )
                        .join(", ")}`
                    : "."
                }`;
  const next = !scan
    ? "Discover media, then analyze and compare files."
    : stopped
      ? scan.status === "cancelled"
        ? "Start a new scan when ready."
        : "Resume the saved scan to continue."
      : current === 1
        ? "Analyze files and show matches as they are found."
        : current === 2
          ? "Finalize groups; you can already review live matches below."
          : current === 3
            ? "Review the final groups and confirm any cleanup."
            : "Open a read-only cleanup review, then confirm deletion.";
  return (
    <section className="scan-workflow" aria-label="Scan workflow">
      <ol>
        {steps.map((step, index) => (
          <li
            key={step}
            className={
              index < current
                ? "done"
                : index === current
                  ? "current"
                  : "upcoming"
            }
            aria-current={index === current ? "step" : undefined}
          >
            <span className="scan-step-number">
              {index < current ? "✓" : index + 1}
            </span>
            <span>
              {step}
              <small>
                {index < current
                  ? "Done"
                  : index === current
                    ? stopped
                      ? "Stopped"
                      : current === 4
                        ? "Ready"
                        : !scan
                          ? "Start here"
                          : scan.status === "queued"
                            ? "Queued"
                            : "In progress"
                    : index === current + 1
                      ? "Next"
                      : "Later"}
              </small>
            </span>
          </li>
        ))}
      </ol>
      <div className="scan-workflow-status" aria-live="polite">
        <p>
          <strong>Now:</strong> {now}
        </p>
        <p>
          <strong>Next:</strong> {next}
        </p>
      </div>
    </section>
  );
}
