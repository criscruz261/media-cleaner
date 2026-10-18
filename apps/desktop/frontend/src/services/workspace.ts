export const workspaceKey = "media-cleaner.workspace.v1";
export const draftKey = "media-cleaner.scan-draft.v1";
const pages = ["Dashboard", "Scanner", "Review", "Cleanup", "Settings"];
export function loadWorkspace(): { page: string; scanId: string } {
  try {
    const value = JSON.parse(localStorage.getItem(workspaceKey) ?? "null");
    return {
      page: pages.includes(value?.page) ? value.page : "Dashboard",
      scanId: typeof value?.scanId === "string" ? value.scanId : "",
    };
  } catch {
    return { page: "Dashboard", scanId: "" };
  }
}
export function saveLocal(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Server checkpoints still work when browser storage is disabled. */
  }
}
type ScanDraft = {
  roots: string;
  excluded: string;
  extensions: string;
  hidden: boolean;
  mode: string;
  sensitivity: string;
  videoSamples: number;
};
export function loadDraft(): ScanDraft {
  const defaults = {
    roots: "",
    excluded: "",
    extensions: "",
    hidden: false,
    mode: "similar",
    sensitivity: "balanced",
    videoSamples: 9,
  };
  try {
    const value = JSON.parse(localStorage.getItem(draftKey) ?? "null");
    if (!value) return defaults;
    return {
      roots: typeof value.roots === "string" ? value.roots : "",
      excluded: typeof value.excluded === "string" ? value.excluded : "",
      extensions: typeof value.extensions === "string" ? value.extensions : "",
      hidden: value.hidden === true,
      mode: ["similar", "exact", "images", "videos"].includes(value.mode)
        ? value.mode
        : "similar",
      videoSamples:
        Number.isInteger(value.videoSamples) &&
        value.videoSamples >= 6 &&
        value.videoSamples <= 24
          ? value.videoSamples
          : 9,
      sensitivity: [
        "strict",
        "balanced",
        "broad",
        "very_loose",
        "extra_loose",
        "maximum",
      ].includes(value.sensitivity)
        ? value.sensitivity
        : "balanced",
    };
  } catch {
    return defaults;
  }
}
