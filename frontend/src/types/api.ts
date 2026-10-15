export type Page<T> = { items: T[]; total: number };
export type Scan = {
  id: string;
  status: string;
  stage: string;
  discovered: number;
  processed: number;
  bytes_processed: number;
  cache_hits: number;
  errors: number;
  error: string | null;
  created_at: string;
  options: { roots: string[] };
};
export type MediaFile = {
  id: string;
  name: string;
  path: string;
  size: number;
  sha256: string;
  status: string;
  media_type: "image" | "video";
  keep: boolean;
  protected_reason: string | null;
  metadata: Record<string, unknown>;
  warnings: string[];
};
export type Group = {
  id: string;
  scan_id: string;
  classification: string;
  evidence: { sha256: string; algorithm: string };
  recommendation: string;
  recommended_id: string | null;
  recoverable: number;
  member_count: number;
  review_status: string;
  files?: MediaFile[];
};
export type CleanupItem = {
  file_id: string;
  source: string;
  keeper: string;
  size: number;
  status: string;
  quarantine_path: string | null;
  error: string | null;
};
export type Cleanup = {
  id: string;
  status: string;
  token: string;
  destination: "trash" | "quarantine";
  items: CleanupItem[];
  total_bytes: number;
  created_at: string;
  expires_at: string;
};
export type Settings = {
  protected_directories: string[];
  excluded_directories: string[];
  excluded_extensions: string[];
  include_hidden: boolean;
  concurrency: number;
  cleanup_destination: "trash" | "quarantine";
  theme: "system" | "light" | "dark";
};
