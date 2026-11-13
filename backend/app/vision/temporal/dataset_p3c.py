"""
P3C dataset quality primitives: duplicate detection, annotation audit, split leakage.

All functions are pure — they accept in-memory records and return results.
No file I/O. No model calls.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


class ConflictType(str, Enum):
    CROSS_SPLIT_LEAKAGE = "CROSS_SPLIT_LEAKAGE"
    LABEL_CONFLICT = "LABEL_CONFLICT"
    BOTH = "BOTH"
    SAME_LABEL_SAME_SPLIT = "SAME_LABEL_SAME_SPLIT"


class ContaminationLevel(str, Enum):
    CLEAN = "CLEAN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class ImageRecord:
    image_path: str
    sha1_16: str
    label: str
    split: str
    red_markup_ratio: float = 0.0
    green_markup_ratio: float = 0.0
    blue_markup_ratio: float = 0.0


@dataclass(frozen=True)
class DuplicatePair:
    sha1_16: str
    path_a: str
    path_b: str
    label_a: str
    label_b: str
    split_a: str
    split_b: str
    conflict_type: ConflictType


def _is_cross_split(split_a: str, split_b: str) -> bool:
    splits = {split_a, split_b}
    return "test" in splits and len(splits) > 1


def _classify_conflict(label_a: str, label_b: str, split_a: str, split_b: str) -> ConflictType:
    cross = _is_cross_split(split_a, split_b)
    conflict = label_a != label_b
    if cross and conflict:
        return ConflictType.BOTH
    if cross:
        return ConflictType.CROSS_SPLIT_LEAKAGE
    if conflict:
        return ConflictType.LABEL_CONFLICT
    return ConflictType.SAME_LABEL_SAME_SPLIT


def find_duplicate_pairs(records: list[ImageRecord]) -> list[DuplicatePair]:
    """Return all ordered pairs (a < b by path) that share the same SHA1."""
    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for r in records:
        groups[r.sha1_16].append(r)

    pairs: list[DuplicatePair] = []
    for sha1, group in groups.items():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda r: r.image_path)
        for i in range(len(sorted_group)):
            for j in range(i + 1, len(sorted_group)):
                a, b = sorted_group[i], sorted_group[j]
                pairs.append(DuplicatePair(
                    sha1_16=sha1,
                    path_a=a.image_path,
                    path_b=b.image_path,
                    label_a=a.label,
                    label_b=b.label,
                    split_a=a.split,
                    split_b=b.split,
                    conflict_type=_classify_conflict(a.label, b.label, a.split, b.split),
                ))
    return pairs


def classify_annotation_contamination(
    red: float, green: float, blue: float
) -> ContaminationLevel:
    """Classify image annotation contamination from per-channel markup ratios."""
    mx = max(red, green, blue)
    if mx == 0.0:
        return ContaminationLevel.CLEAN
    if mx <= 0.01:
        return ContaminationLevel.LOW
    if mx <= 0.05:
        return ContaminationLevel.MEDIUM
    return ContaminationLevel.HIGH


def find_leaked_test_records(records: list[ImageRecord]) -> list[ImageRecord]:
    """Return test records whose SHA1 also appears in train or val."""
    train_val_sha1s = {r.sha1_16 for r in records if r.split in ("train", "val")}
    return [r for r in records if r.split == "test" and r.sha1_16 in train_val_sha1s]


def leakage_free_test_records(records: list[ImageRecord]) -> list[ImageRecord]:
    """Return test records with no SHA1 in train or val."""
    train_val_sha1s = {r.sha1_16 for r in records if r.split in ("train", "val")}
    return [r for r in records if r.split == "test" and r.sha1_16 not in train_val_sha1s]


def has_cross_split_leakage(records: list[ImageRecord]) -> bool:
    return len(find_leaked_test_records(records)) > 0


def label_conflict_sha1s(records: list[ImageRecord]) -> set[str]:
    """Return SHA1s where the same image carries different labels."""
    groups: dict[str, set[str]] = defaultdict(set)
    for r in records:
        groups[r.sha1_16].add(r.label)
    return {sha1 for sha1, labels in groups.items() if len(labels) > 1}


def unverified_label_sha1s(records: list[ImageRecord]) -> set[str]:
    """Return SHA1s present in both a specific-defect class and 'generic_bad'."""
    groups: dict[str, set[str]] = defaultdict(set)
    for r in records:
        groups[r.sha1_16].add(r.label)
    result: set[str] = set()
    for sha1, labels in groups.items():
        if "generic_bad" in labels and len(labels) > 1:
            result.add(sha1)
    return result
