"""Duration-bucket and frame-hash indexing with complete-link sequence groups."""

from collections import Counter
from dataclasses import dataclass, field
import json
import math
from sqlalchemy import select, delete
from app.database.models import File, Fingerprint, DuplicateGroup, GroupMember, SimilarityMatch
from app.similarity.images import HashIndex, PRESETS
from app.similarity.temporal import ALGORITHM, VERSION, MIN_MATCHES, duration_tolerance, compare_sequences


def bucket(duration: float) -> int:
    return math.floor(math.log(max(duration, 0.25)) / 0.03)


class SequenceIndex:
    def __init__(self):
        self.buckets: dict[int, dict[int, HashIndex]] = {}

    def add(self, value: dict, group_id: str):
        indexes = self.buckets.setdefault(bucket(value["duration"]), {})
        for frame in value["frames"]:
            indexes.setdefault(frame["slot"], HashIndex()).add(int(frame["phash"], 16), group_id)

    def candidates(self, value: dict, sensitivity: str):
        tolerance = duration_tolerance(value["duration"], sensitivity)
        votes = Counter()
        for number in range(
            bucket(max(0.25, value["duration"] - tolerance)), bucket(value["duration"] + tolerance) + 1
        ):
            indexes = self.buckets.get(number, {})
            for frame in value["frames"]:
                index = indexes.get(frame["slot"])
                if index:
                    votes.update(index.search(int(frame["phash"], 16), PRESETS[sensitivity][0]))
        return [group_id for group_id, count in votes.items() if count >= MIN_MATCHES]


@dataclass
class SequenceCluster:
    id: str
    representative: str
    digest: str
    anchor: dict
    descriptors: dict[str, dict] = field(default_factory=dict)
    digests: set[str] = field(default_factory=set)
    kinds: set[str] = field(default_factory=set)
    count: int = 0
    total: int = 0
    largest: int = 0
    minimum_matched: int = 9
    maximum_duration_difference: float = 0


def build_sequence_groups(session, scan_id, sensitivity, checkpoint):
    index, clusters = SequenceIndex(), {}
    query = (
        select(File.id, File.size, File.sha256, Fingerprint.value)
        .join(Fingerprint, Fingerprint.file_id == File.id)
        .where(
            File.scan_id == scan_id,
            File.status == "ready",
            Fingerprint.algorithm == ALGORITHM,
            Fingerprint.version == VERSION,
        )
        .order_by(File.path)
        .execution_options(yield_per=128)
    )
    for file_id, size, digest, value in session.execute(query):
        checkpoint()
        if "frames" not in value:
            continue
        target = None
        matches = []
        for candidate_id in index.candidates(value, sensitivity):
            checkpoint()
            candidate = clusters[candidate_id]
            matches = [
                compare_sequences(value, previous, sensitivity) for previous in candidate.descriptors.values()
            ]
            if all(match is not None for match in matches):
                target = candidate
                break
        if target is None:
            group = DuplicateGroup(
                scan_id=scan_id,
                classification="SIMILAR_CONTENT",
                evidence={},
                recommended_id=None,
                recommendation="Similar frame sequences do not prove identical media. Audio may differ. Keep all files until you compare playback.",
                recoverable=0,
                member_count=1,
            )
            session.add(group)
            session.flush()
            target = SequenceCluster(group.id, file_id, digest, value)
            clusters[group.id] = target
            index.add(value, group.id)
        else:
            target.minimum_matched = min(
                target.minimum_matched, *(match["matched_samples"] for match in matches)
            )
            target.maximum_duration_difference = max(
                target.maximum_duration_difference,
                *(match["duration_difference_seconds"] for match in matches),
            )
            if digest != target.digest:
                evidence = compare_sequences(value, target.anchor, sensitivity)
                session.add(
                    SimilarityMatch(
                        left_id=target.representative,
                        right_id=file_id,
                        classification="SIMILAR_CONTENT",
                        evidence=evidence,
                    )
                )
        target.descriptors.setdefault(json.dumps(value, sort_keys=True), value)
        target.digests.add(digest)
        target.kinds.add(value["kind"])
        target.count += 1
        target.total += size
        target.largest = max(target.largest, size)
        session.add(GroupMember(group_id=target.id, file_id=file_id, keep=True))
        session.flush()
    for cluster in clusters.values():
        checkpoint()
        if cluster.count < 2 or len(cluster.digests) < 2:
            session.execute(delete(GroupMember).where(GroupMember.group_id == cluster.id))
            session.execute(delete(DuplicateGroup).where(DuplicateGroup.id == cluster.id))
            continue
        group = session.get(DuplicateGroup, cluster.id)
        group.member_count, group.recoverable = cluster.count, cluster.total - cluster.largest
        group.evidence = {
            "algorithm": ALGORITHM,
            "version": VERSION,
            "media_kind": "sequence",
            "member_kinds": sorted(cluster.kinds),
            "sample_count": 9,
            "minimum_matched_samples": cluster.minimum_matched,
            "max_duration_difference_seconds": cluster.maximum_duration_difference,
            "phash_limit": PRESETS[sensitivity][0],
            "dhash_limit": PRESETS[sensitivity][1],
            "sensitivity": sensitivity,
            "grouping": "complete-link",
            "note": "Time-spaced visual samples only; audio and unsampled moments may differ. This does not detect arbitrary trims or partial overlap.",
        }
    checkpoint()
    session.commit()
