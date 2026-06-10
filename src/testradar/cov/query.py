from __future__ import annotations


def query_dynamic_contexts(*args, **kwargs) -> None:
    raise NotImplementedError(
        "Dynamic coverage-context queries are deferred until static-only analysis is proven.",
    )
