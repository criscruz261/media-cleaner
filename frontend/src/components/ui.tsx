import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight, LoaderCircle, ShieldCheck } from "lucide-react";
export function ErrorMessage({ error }: { error: unknown }) {
  return error ? (
    <p className="error" role="alert">
      {error instanceof Error ? error.message : String(error)}
    </p>
  ) : null;
}
export function Loading() {
  return (
    <p className="muted flex items-center gap-2">
      <LoaderCircle size={16} className="animate-spin" /> Loading local data…
    </p>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <ShieldCheck size={32} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Pagination({
  offset,
  total,
  size,
  onChange,
}: {
  offset: number;
  total: number;
  size: number;
  onChange: (offset: number) => void;
}) {
  return total > size ? (
    <div className="pagination">
      <button
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - size))}
      >
        <ArrowLeft size={14} /> Previous
      </button>
      <span>
        {offset + 1}–{Math.min(offset + size, total)} of {total}
      </span>
      <button
        disabled={offset + size >= total}
        onClick={() => onChange(offset + size)}
      >
        Next <ArrowRight size={14} />
      </button>
    </div>
  ) : null;
}
