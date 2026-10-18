# Local subject and scene matching

Both platforms bundle Google's MobileNet V3 Small image embedder and MediaPipe
(Python 0.10.32, Android 0.10.21). The model runs locally on the CPU; scanning never uploads media or
fetches weights. Source: https://developers.google.com/edge/mediapipe/solutions/vision/image_embedder

Model artifact (version 1):
https://storage.googleapis.com/mediapipe-models/image_embedder/mobilenet_v3_small/float32/1/mobilenet_v3_small.tflite

SHA-256: `bbbb4c51a55a53905af1daec995ca1aae355046f8839bb8c9f5ce9271394bc40`

Model family/license: https://www.kaggle.com/models/google/mobilenet-v3
Apache 2.0; license included beside the model on both platforms.

Descriptors contain normalized, signed-byte learned features for the whole
image and four image quadrants, plus the existing perceptual hashes. A metric
index retrieves candidates beyond whole-image hash agreement. Every member must
still match every other member; no similarity chains and no automatic selection
of approximate matches for deletion.

| Sensitivity | Whole-image cosine threshold | Shared-region fallback |
| --- | --- | --- |
| Strict | Disabled; original hash checks | Disabled |
| Balanced | 0.98 | Disabled |
| Loose | 0.95 | Disabled |
| Very loose | 0.91 | Two corresponding regions ≥ 0.97 |
| Extra loose | 0.86 | Two corresponding regions ≥ 0.94 |
| Maximum | 0.80 | Two corresponding regions ≥ 0.90 |

Region matches also require whole-image cosine ≥ 0.40 to retain scene context.
These thresholds are heuristics, not calibrated probabilities. Learned features
can find changed poses, framing, viewpoints and backgrounds; shared regions help
when objects are absent or obscured. They cannot prove the same person's or
object's identity and cannot guarantee every transformation will match. Similar
classes of objects can produce false positives at looser levels.

Video/animation frames use the same features while retaining duration and
multi-frame agreement checks. Exact matching still uses SHA-256. Descriptor
versions changed so older hashes-only caches are recomputed as needed, including
when continuing an older checkpoint. No source files or cleanup history are removed.

Android is pinned to 0.10.21 to avoid the Apple Silicon ARM emulator SIGILL
regression tracked at https://github.com/google-ai-edge/mediapipe/issues/6293.
