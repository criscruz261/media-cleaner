import { useCompactGroups } from "./CompactGroupsContext";
import { createContext, useContext, useState, type ReactNode } from "react";
export type GroupFilter = "" | "EXACT_DUPLICATE" | "SIMILAR_CONTENT";
export const GroupFilterContext = createContext<
  [GroupFilter, (value: GroupFilter) => void] | null
>(null);
export function useGroupFilter() {
  const shared = useContext(GroupFilterContext);
  const local = useState<GroupFilter>("");
  return shared ?? local;
}
export function GroupFilters({
  classification,
  sort,
  onChange,
  children,
}: {
  children?: ReactNode;
  classification: GroupFilter;
  sort: string;
  onChange: (classification: GroupFilter, sort: string) => void;
}) {
  const [compact, setCompact] = useCompactGroups();
  return (
    <div
      className="group-actions group-toolbar"
      role="region"
      aria-label="Group review controls"
    >
      {children}
      <label>
        Show groups{" "}
        <select
          aria-label="Filter groups"
          value={classification}
          onChange={(event) =>
            onChange(event.target.value as GroupFilter, sort)
          }
        >
          <option value="">All matches</option>
          <option value="EXACT_DUPLICATE">Exact duplicates only</option>
          <option value="SIMILAR_CONTENT">Similar media only</option>
        </select>
      </label>
      <label>
        Sort groups{" "}
        <select
          aria-label="Sort groups"
          value={sort}
          onChange={(event) => onChange(classification, event.target.value)}
        >
          <option value="discovered">Discovery order</option>
          <option value="exact_first">Exact duplicates first</option>
          <option value="largest">Most recoverable space</option>
          <option value="most_files">Most files</option>
        </select>
      </label>
      <label>
        Compact level{" "}
        <select
          aria-label="Compact level"
          value={compact}
          onChange={(event) => setCompact(Number(event.target.value))}
        >
          <option value={1}>1 · Spacious</option>
          <option value={2}>2 · Balanced</option>
          <option value={3}>3 · Compact</option>
          <option value={4}>4 · Very compact</option>
          <option value={5}>5 · Most compact</option>
        </select>
      </label>
      <p className="hint">
        Sorting applies across all pages. During scanning, groups may move when
        their size changes; discovery order keeps new groups at the end.
      </p>
    </div>
  );
}
