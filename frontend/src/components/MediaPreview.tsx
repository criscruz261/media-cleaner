import { useState } from "react";
import { ExternalLink, ZoomIn } from "lucide-react";
import { prefix } from "../services/api";
import type { MediaFile } from "../types/api";
export function MediaPreview({ file }: { file: MediaFile }) {
  const [failed, setFailed] = useState(false),
    [zoom, setZoom] = useState(false);
  const url = `${prefix}/files/${file.id}/preview`;
  return (
    <>
      <div className="preview">
        {failed ? (
          <p>Preview unavailable for this format. Exact hashing still works.</p>
        ) : file.media_type === "video" ? (
          <video
            controls
            preload="none"
            playsInline
            src={url}
            aria-label={file.name}
            onError={() => setFailed(true)}
          />
        ) : (
          <button
            className="image-button"
            aria-label={`Enlarge ${file.name}`}
            onClick={() => setZoom(true)}
          >
            <img
              loading="lazy"
              src={url}
              alt={file.name}
              onError={() => setFailed(true)}
            />
            <ZoomIn size={16} />
          </button>
        )}
      </div>
      <a className="small-link" href={url} target="_blank" rel="noreferrer">
        Open preview <ExternalLink size={12} />
      </a>
      {zoom && (
        <div className="modal-backdrop" onClick={() => setZoom(false)}>
          <section
            className="zoom-modal"
            role="dialog"
            aria-modal="true"
            aria-label={file.name}
          >
            <button autoFocus onClick={() => setZoom(false)}>
              Close preview
            </button>
            <img src={url} alt={file.name} />
          </section>
        </div>
      )}
    </>
  );
}
