"""Pick the reranker to run when a configuration names one.

The default configuration names Cohere; without an API key it returns the list
unchanged, so the setting read "reranking on" while nothing was re-ranked. Instead of
leaving that as a silent no-op, an unavailable reranker falls back to the local
lexical one (``kotaemon.rerankings.local_lexical``), which needs no key, no model and
no network. The substitution is logged, and ``tools/doctor.py`` still reports that the
configured provider has no credentials.
"""

from __future__ import annotations

from typing import Callable, Optional

from .base import BaseReranking
from .local_lexical import LocalLexicalReranker


def resolve_reranker(
    configured: Optional[str],
    get_model: Callable[[str], Optional[BaseReranking]],
) -> BaseReranking:
    """Return a reranker that can actually run.

    Args:
        configured: name from the index/reranking setting (may be empty)
        get_model: looks a name up in the model pool (``None`` when absent)
    """
    model = get_model(configured) if configured else None
    if model is not None and model.is_available():
        return model

    name = configured or "(default)"
    print(
        f"Reranking: {name} is not usable here, falling back to the local lexical "
        "reranker"
    )
    return LocalLexicalReranker()
