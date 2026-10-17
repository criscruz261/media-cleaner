import { usePopupKeyboard } from "./usePopupKeyboard";
import { useState } from "react";
import { ExternalLink, ZoomIn, Play } from "lucide-react";
import { prefix } from "../services/api";
import type { MediaFile } from "../types/api";
export function MediaPreview({
  file,
  thumbnailFirst = false,
  onOpen,
}: {
  file: MediaFile;
  thumbnailFirst?: boolean;
  onOpen?: () => void;
}) {
  const [playing, setPlaying] = useState(false);
  const [thumbnailFailed, setThumbnailFailed] = useState(false);
  const thumbnail = `${prefix}/files/${file.id}/thumbnail`;
  const [failed, setFailed] = useState(false),
    [zoom, setZoom] = useState(false);
  const url = `${prefix}/files/${file.id}/preview`;
  usePopupKeyboard(zoom, (event) => {
    if (event.key === "Escape") setZoom(false);
  });
  return (
    <>
      <div className="preview">
        {failed ? (
          <p>Preview unavailable for this format. Exact hashing still works.</p>
        ) : file.media_type === "video" && thumbnailFirst && !playing ? (
          <button
            className="image-button video-thumbnail"
            aria-label={`Play ${file.name}`}
            onClick={() => setPlaying(true)}
          >
            {thumbnailFailed ? (
              <span>Thumbnail unavailable · Play video</span>
            ) : (
              <img
                loading="lazy"
                src={thumbnail}
                alt={`Thumbnail of ${file.name}`}
                onError={() => setThumbnailFailed(true)}
              />
            )}
            <Play size={28} />
          </button>
        ) : file.media_type === "video" ? (
          <video
            controls
            autoPlay={thumbnailFirst && playing}
            poster={`${prefix}/files/${file.id}/thumbnail`}
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
            onClick={() => (onOpen ? onOpen() : setZoom(true))}
          >
            <img
              loading="lazy"
              src={thumbnailFirst ? thumbnail : url}
              alt={file.name}
              onError={() => setFailed(true)}
            />
            <ZoomIn size={16} />
          </button>
        )}
      </div>
      {onOpen ? (
        <button className="small-link" onClick={onOpen}>
          Open group preview
        </button>
      ) : (
        <a className="small-link" href={url} target="_blank" rel="noreferrer">
          Open preview <ExternalLink size={12} />
        </a>
      )}
      {zoom && (
        <div className="modal-backdrop" onClick={() => setZoom(false)}>
          <section
            className="zoom-modal"
            onClick={(event) => event.stopPropagation()}
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
