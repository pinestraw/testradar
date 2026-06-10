from __future__ import annotations

import ast
from pathlib import Path
from typing import Protocol, Sequence

from testradar.models import ImportRequest


class CouplingDetector(Protocol):
    name: str

    def detect(
        self,
        *,
        tree: ast.AST,
        path: Path,
        module: str | None,
    ) -> Sequence[ImportRequest]:
        ...
