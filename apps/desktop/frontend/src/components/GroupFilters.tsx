export type GroupFilter = "" | "EXACT_DUPLICATE" | "SIMILAR_CONTENT";
export function GroupFilters({
  classification,
  sort,
  onChange,
}: {
  classification: GroupFilter;
  sort: string;
  onChange: (classification: GroupFilter, sort: string) => void;
}) {
  return (
    <div className="group-actions">
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
      <p className="hint">
        Sorting applies across all pages. During scanning, groups may move when
        their size changes; discovery order keeps new groups at the end.
      </p>
    </div>
  );
}
