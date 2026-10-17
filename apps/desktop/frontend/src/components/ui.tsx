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
  onSizeChange,
}: {
  offset: number;
  total: number;
  size: number;
  onChange: (offset: number) => void;
  onSizeChange?: (size: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  const page = Math.min(pages, Math.floor(offset / size) + 1);
  return total > size || onSizeChange ? (
    <div className="pagination">
      {onSizeChange && (
        <label>
          Groups per page{" "}
          <select
            aria-label="Groups per page"
            value={size}
            onChange={(event) => onSizeChange(Number(event.target.value))}
          >
            {[
              ...new Set([
                5,
                10,
                20,
                50,
                100,
                size,
                ...(total > 0 ? [total] : []),
              ]),
            ]
              .sort((a, b) => a - b)
              .map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
          </select>
        </label>
      )}
      {onSizeChange && (
        <button disabled={!offset} onClick={() => onChange(0)}>
          First
        </button>
      )}
      <button
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - size))}
      >
        <ArrowLeft size={14} /> Previous
      </button>
      <span>
        {total ? offset + 1 : 0}–{Math.min(offset + size, total)} of {total}
      </span>
      <button
        disabled={offset + size >= total}
        onClick={() => onChange(offset + size)}
      >
        Next <ArrowRight size={14} />
      </button>
      {onSizeChange && (
        <>
          <button
            disabled={offset + size >= total}
            onClick={() => onChange((pages - 1) * size)}
          >
            Last
          </button>
          <form
            className="pagination-jump"
            onSubmit={(event) => {
              event.preventDefault();
              const input = event.currentTarget.elements.namedItem(
                "page",
              ) as HTMLInputElement;
              if (Number.isFinite(input.valueAsNumber))
                onChange(
                  (Math.min(
                    pages,
                    Math.max(1, Math.floor(input.valueAsNumber)),
                  ) -
                    1) *
                    size,
                );
            }}
          >
            <label>
              Page{" "}
              <input
                key={`${offset}:${size}`}
                aria-label="Page number"
                name="page"
                type="number"
                min={1}
                max={pages}
                step={1}
                defaultValue={page}
                required
              />
            </label>
            <span>of {pages}</span>
            <button type="submit">Go</button>
          </form>
        </>
      )}
    </div>
  ) : null;
}
