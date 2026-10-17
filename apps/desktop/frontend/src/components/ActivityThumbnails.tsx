import { useState } from "react";
import { prefix } from "../services/api";
import type { Scan } from "../types/api";

function ActivityThumbnail({
  item,
}: {
  item: NonNullable<Scan["activity"]>[number];
}) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const name = item.path.split(/[\\/]/).pop() ?? item.path;
  return (
    <figure className="activity-thumbnail">
      <div className="activity-thumbnail-image">
        {item.file_id && !failed ? (
          <>
            {!loaded && <span>Loading preview…</span>}
            <img
              src={`${prefix}/files/${item.file_id}/thumbnail`}
              alt={`Processing ${name}`}
              onLoad={() => setLoaded(true)}
              onError={() => setFailed(true)}
            />
          </>
        ) : (
          <span>Preview unavailable</span>
        )}
      </div>
      <figcaption title={item.path}>{name}</figcaption>
    </figure>
  );
}
export function ActivityThumbnails({
  activity,
}: {
  activity: NonNullable<Scan["activity"]>;
}) {
  return (
    <div className="activity-thumbnails" aria-label="Files being processed">
      {activity.map((item) => (
        <ActivityThumbnail key={item.file_id ?? item.path} item={item} />
      ))}
    </div>
  );
}
