"""Versioned image descriptors and indexed, conservative similarity grouping."""

from dataclasses import dataclass, field
from pathlib import Path
import math
import base64
from app.similarity import subjects
import imagehash
from PIL import Image, ImageStat
from sqlalchemy import delete
from app.database.models import ScanJob, now, DuplicateGroup, GroupMember, SimilarityMatch

from app.grouping.records import fingerprint_records

ALGORITHM = "imagehash-phash-dhash"
VERSION = "3"
PRESETS = {
    "strict": (4, 6),
    "balanced": (8, 10),
    "broad": (12, 14),
    "very_loose": (16, 18),
    "extra_loose": (20, 22),
    "maximum": (24, 26),
}


def describe_image(image: Image.Image) -> dict | None:
    image = image.copy()
    image.thumbnail((512, 512))
    image = image.convert("RGB")
    if ImageStat.Stat(image.convert("L")).stddev[0] < 8:
        return None
    return {
        "phash": str(imagehash.phash(image, hash_size=8)),
        "dhash": str(imagehash.dhash(image, hash_size=8)),
        "aspect": image.width / image.height,
        "color": ImageStat.Stat(image.resize((32, 32))).mean,
        "embedding": subjects.describe(image),
        "embedding_model": subjects.MODEL,
        "regions": subjects.regions(image),
    }


def fingerprint_image(path: Path) -> dict:
    from app.metadata.decoding import load_still

    descriptor = describe_image(load_still(path))
    return descriptor or {
        "skipped": "Too little visual detail for reliable perceptual comparison; exact matching remains available."
    }


class HashIndex:
    """BK-tree over unique pHash values; identical hashes share one node."""

    def __init__(self):
        self.root = None

    def add(self, value: int, group_id: str):
        node = self.root
        if node is None:
            self.root = [value, [group_id], {}]
            return
        while True:
            distance = (node[0] ^ value).bit_count()
            if distance == 0:
                node[1].append(group_id)
                return
            if distance not in node[2]:
                node[2][distance] = [value, [group_id], {}]
                return
            node = node[2][distance]

    def search(self, value: int, radius: int):
        stack = [self.root] if self.root else []
        while stack:
            node = stack.pop()
            distance = (node[0] ^ value).bit_count()
            if distance <= radius:
                yield from node[1]
            stack.extend(
                child for edge, child in node[2].items() if distance - radius <= edge <= distance + radius
            )


@dataclass(frozen=True)
class Signature:
    phash: int
    dhash: int
    aspect: float
    color: tuple[float, ...]
    embedding: bytes = b""
    regions: tuple[bytes, ...] = ()

    @classmethod
    def from_value(cls, value):
        return cls(
            int(value["phash"], 16),
            int(value["dhash"], 16),
            value["aspect"],
            tuple(value["color"]),
            base64.b64decode(value.get("embedding", "")),
            tuple(base64.b64decode(region) for region in value.get("regions", [])),
        )

    def distances(self, other):
        return ((self.phash ^ other.phash).bit_count(), (self.dhash ^ other.dhash).bit_count())

    def compatible(self, other, thresholds):
        p, d = self.distances(other)
        limit = subjects.LIMITS[thresholds[0]]
        score = subjects.cosine(self.embedding, other.embedding) if limit is not None else -1
        if limit is not None and (
            score >= limit or subjects.compatible_regions(self.regions, other.regions, score, thresholds[0])
        ):
            return True
        return (
            p <= thresholds[0]
            and d <= thresholds[1]
            and abs(math.log(self.aspect / other.aspect)) <= 0.1
            and max(abs(a - b) for a, b in zip(self.color, other.color)) <= 60
        )


@dataclass
class Cluster:
    id: str
    representative: str
    anchor: Signature
    representative_digest: str
    signatures: set[Signature] = field(default_factory=set)
    digests: set[str] = field(default_factory=set)
    count: int = 0
    total_bytes: int = 0
    largest: int = 0
    max_phash: int = 0
    max_dhash: int = 0


def image_matcher(session, scan_id, sensitivity, checkpoint):
    thresholds = PRESETS[sensitivity]
    index, subject_index, clusters = HashIndex(), subjects.SubjectIndex(), {}
    while True:
        record = yield
        if record is None:
            break
        file_id, size, digest, value = record
        checkpoint()
        if "phash" not in value:
            session.commit()
            continue
        signature = Signature.from_value(value)
        target = None
        candidates = dict.fromkeys(index.search(signature.phash, thresholds[0]))
        for vector in (signature.embedding, *signature.regions):
            candidates.update(dict.fromkeys(subject_index.search(vector, subjects.LIMITS[thresholds[0]])))
        for candidate_id in candidates:
            candidate = clusters[candidate_id]
            # Complete-link constraints: every unique descriptor must agree. No weak chains.
            if all(signature.compatible(other, thresholds) for other in candidate.signatures):
                target = candidate
                break
        if target is None:
            group = DuplicateGroup(
                scan_id=scan_id,
                classification="SIMILAR_CONTENT",
                evidence={},
                recommended_id=None,
                recommendation="Similar appearance is not proof of duplication. All files are kept; choose manually after comparing.",
                recoverable=0,
                member_count=1,
            )
            session.add(group)
            session.flush()
            target = Cluster(group.id, file_id, signature, digest)
            clusters[group.id] = target
            index.add(signature.phash, group.id)
            if subjects.LIMITS[thresholds[0]] is not None:
                for vector in (signature.embedding, *signature.regions):
                    subject_index.add(vector, group.id)
        else:
            for other in target.signatures:
                p, d = signature.distances(other)
                target.max_phash = max(target.max_phash, p)
                target.max_dhash = max(target.max_dhash, d)
            if digest != target.representative_digest:
                p, d = signature.distances(target.anchor)
                session.add(
                    SimilarityMatch(
                        left_id=target.representative,
                        right_id=file_id,
                        classification="SIMILAR_CONTENT",
                        evidence={
                            "algorithm": ALGORITHM,
                            "version": VERSION,
                            "phash_distance": p,
                            "dhash_distance": d,
                            "phash_limit": thresholds[0],
                            "dhash_limit": thresholds[1],
                        },
                    )
                )
        target.signatures.add(signature)
        target.digests.add(digest)
        target.count += 1
        target.total_bytes += size
        target.largest = max(target.largest, size)
        live_group = session.get(DuplicateGroup, target.id)
        live_group.member_count = target.count
        live_group.recoverable = target.total_bytes - target.largest
        live_group.updated_at = now()
        if target.count < 2 or len(target.digests) < 2:
            live_group.review_status = "pending"
        elif live_group.review_status != "reviewed":
            live_group.review_status = "unreviewed"
        live_group.evidence = {
            "algorithm": ALGORITHM,
            "version": VERSION,
            "hash_bits": 64,
            "sensitivity": sensitivity,
            "phash_limit": thresholds[0],
            "dhash_limit": thresholds[1],
            "max_phash_distance": target.max_phash,
            "max_dhash_distance": target.max_dhash,
            "grouping": "complete-link",
            "subject_cosine_limit": subjects.LIMITS[thresholds[0]],
            "embedding_model": subjects.MODEL,
            "note": "Perceptual hashes or learned visual similarity; not identity recognition or proof of duplication.",
        }
        session.add(GroupMember(group_id=target.id, file_id=file_id, keep=True))
        session.flush()
        session.get(ScanJob, scan_id).updated_at = now()
        session.commit()
    for cluster in clusters.values():
        checkpoint()
        if cluster.count < 2 or len(cluster.digests) < 2:
            session.execute(delete(GroupMember).where(GroupMember.group_id == cluster.id))
            session.execute(delete(DuplicateGroup).where(DuplicateGroup.id == cluster.id))
            continue
        group = session.get(DuplicateGroup, cluster.id)
        group.member_count = cluster.count
        group.recoverable = cluster.total_bytes - cluster.largest
        group.evidence = {
            "algorithm": ALGORITHM,
            "version": VERSION,
            "hash_bits": 64,
            "sensitivity": sensitivity,
            "phash_limit": thresholds[0],
            "dhash_limit": thresholds[1],
            "max_phash_distance": cluster.max_phash,
            "max_dhash_distance": cluster.max_dhash,
            "grouping": "complete-link",
            "subject_cosine_limit": subjects.LIMITS[thresholds[0]],
            "embedding_model": subjects.MODEL,
            "note": "Perceptual hashes or learned visual similarity; not identity recognition or proof of duplication.",
        }
    checkpoint()
    session.commit()


def build_similar_groups(session, scan_id, sensitivity, checkpoint):
    matcher = image_matcher(session, scan_id, sensitivity, checkpoint)
    next(matcher)
    for record in fingerprint_records(session, scan_id, ALGORITHM, VERSION):
        matcher.send(record)
    try:
        matcher.send(None)
    except StopIteration:
        pass
