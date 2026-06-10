from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SelectionSource(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    GLOBAL = "global"


class ChangeScope(str, Enum):
    IGNORE = "ignore"
    SOURCE = "source"
    TEST = "test"
    GLOBAL = "global"
    SUBTREE = "subtree"
    APP = "app"


@dataclass(frozen=True)
class HunkRange:
    start: int
    count: int

    @property
    def end(self) -> int:
        if self.count <= 0:
            return self.start
        return self.start + self.count - 1

    def overlaps(self, start: int, end: int) -> bool:
        if self.count <= 0:
            return start <= self.start <= end
        return not (self.end < start or self.start > end)


@dataclass(frozen=True)
class FileChange:
    status: str
    path: str
    old_path: Optional[str] = None
    hunks: tuple[HunkRange, ...] = ()
    is_untracked: bool = False

    @property
    def comparison_path(self) -> str:
        return self.old_path or self.path

    @property
    def is_deleted(self) -> bool:
        return self.status == "D"

    @property
    def is_rename(self) -> bool:
        return self.status == "R"

    @property
    def is_added(self) -> bool:
        return self.status == "A" or self.is_untracked


@dataclass(frozen=True)
class ImportRequest:
    module: Optional[str]
    names: tuple[str, ...] = ()
    is_from: bool = False
    is_eager: bool = True


@dataclass
class FileRecord:
    path: str
    content_hash: str
    module: Optional[str]
    is_test: bool
    parse_error: Optional[str]
    imports: tuple[ImportRequest, ...]
    resolved_imports: tuple[str, ...] = ()
    resolved_eager_imports: tuple[str, ...] = ()


@dataclass
class GraphSnapshot:
    version: int
    source_roots: tuple[str, ...]
    files: dict[str, FileRecord]
    module_to_path: dict[str, str]
    reverse_edges: dict[str, tuple[str, ...]]
    repo_fingerprint: str
    updated_paths: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    def python_paths(self) -> set[str]:
        return set(self.files)


@dataclass(frozen=True)
class Classification:
    path: str
    scope: ChangeScope
    reason: str
    anchor: Optional[str] = None
    uses_old_graph: bool = False


@dataclass(frozen=True)
class SelectedTarget:
    target: str
    source: SelectionSource
    reason: str


@dataclass
class SelectionResult:
    targets: list[SelectedTarget]
    reasons: list[str]
    graph_snapshot: GraphSnapshot
    full_suite: bool = False
    graph_mode: str = "unchanged"
    escalations: list[str] = field(default_factory=list)

    def target_strings(self) -> list[str]:
        return [item.target for item in self.targets]


@dataclass(frozen=True)
class NodeSpan:
    nodeid: str
    start: int
    end: int
    has_parametrize: bool
    has_decorators: bool


@dataclass
class AuditResult:
    selected: set[str]
    failed: set[str]
    missed: set[str]

    @property
    def miss_rate(self) -> float:
        if not self.failed:
            return 0.0
        return len(self.missed) / len(self.failed)


def relative_to_root(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
