from __future__ import annotations


def ingest_coverage_contexts(*args, **kwargs) -> None:
    raise NotImplementedError(
        "Dynamic coverage-context ingest is deferred until static-only analysis is proven.",
    )
