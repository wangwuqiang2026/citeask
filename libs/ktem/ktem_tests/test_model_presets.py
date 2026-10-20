"""Shipped model presets: seed only what the user can actually use (§5.34).

The old behaviour wrote every vendor template into the model pool on first run,
including entries whose API key was still ``your-key``. The resources page then
looked like it shipped six "fake" models. These tests pin the replacement rule:
a preset is seeded only when its required secrets are real, and a template still
carrying placeholder credentials is removed instead of shown.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ktem.llms.db import LLMTable
from ktem.utils.model_presets import is_configured, sync_presets


def chat_openai(api_key: str, model: str = "gpt-4o-mini") -> dict:
    return {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "temperature": 0,
        "base_url": "https://api.openai.com/v1",
        "api_key": api_key,
        "model": model,
    }


def embedding_openai(api_key: str) -> dict:
    return {
        "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
        "base_url": "https://api.openai.com/v1",
        "api_key": api_key,
        "model": "text-embedding-3-large",
    }


def test_placeholder_credentials_are_not_configured():
    for placeholder in ("your-key", "<YOUR_OPENAI_KEY>", "", "   "):
        assert is_configured(chat_openai(placeholder)) is False


def test_a_real_api_key_is_configured():
    assert is_configured(chat_openai("sk-real-looking")) is True


def test_a_vendor_without_required_secrets_is_configured():
    # Local models need no credentials: they are usable as they are.
    spec = {"__type__": "kotaemon.rerankings.LocalLexicalReranker"}
    assert is_configured(spec) is True


def test_an_unknown_vendor_is_not_configured():
    assert is_configured({"__type__": "no.such.Vendor"}) is False


def test_sync_prunes_shipped_placeholders_and_keeps_user_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'presets.db'}")
    LLMTable.__table__.create(bind=engine)
    presets = {
        "fake": {"spec": chat_openai("your-key"), "default": True},
        "real": {"spec": chat_openai("sk-real", "gpt-4o"), "default": False},
    }

    with Session(engine) as session:
        # The exact template row older versions wrote on first run.
        session.add(LLMTable(name="fake", spec=chat_openai("your-key"), default=True))
        # A row the user edited (different model) — theirs, never pruned.
        session.add(
            LLMTable(
                name="fake-edited",
                spec=chat_openai("your-key", "gpt-4o"),
                default=False,
            )
        )
        session.add(
            LLMTable(
                name="hand-added",
                spec=chat_openai("sk-user", "gpt-4o-mini"),
                default=False,
            )
        )
        session.commit()
        report = sync_presets(LLMTable, presets, session=session)

    assert report["pruned"] == ["fake"]
    assert report["seeded"] == ["real"]
    with Session(engine) as session:
        rows = {row.name: row for row in session.query(LLMTable).all()}
    assert "fake" not in rows
    assert "fake-edited" in rows, "a spec the user changed is not a template"
    assert "hand-added" in rows
    assert rows["real"].default is False


def test_sync_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'presets.db'}")
    LLMTable.__table__.create(bind=engine)
    presets = {"real": {"spec": chat_openai("sk-real"), "default": True}}

    with Session(engine) as session:
        first = sync_presets(LLMTable, presets, session=session)
    with Session(engine) as session:
        second = sync_presets(LLMTable, presets, session=session)

    assert first["seeded"] == ["real"]
    assert second == {"seeded": [], "pruned": []}
    with Session(engine) as session:
        assert session.query(LLMTable).count() == 1


def test_embedding_presets_follow_the_same_rule(tmp_path):
    """The embedding pool uses the same seeding rule as the chat models (§5.35).

    Upstream wrote all five vendor templates into ``embedding``; three of them
    carried placeholder keys. Seeding must keep the usable ones and drop only the
    exact template rows that cannot run.
    """
    from ktem.embeddings.db import EmbeddingTable

    engine = create_engine(f"sqlite:///{tmp_path / 'presets.db'}")
    EmbeddingTable.__table__.create(bind=engine)
    fast_embed = {
        "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
        "model_name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "batch_size": 64,
    }
    presets = {
        "openai": {"spec": embedding_openai("your-key"), "default": False},
        "fast_embed": {"spec": fast_embed, "default": True},
    }

    with Session(engine) as session:
        # The exact template rows older versions wrote on first run.
        session.add(
            EmbeddingTable(
                name="openai", spec=embedding_openai("your-key"), default=False
            )
        )
        session.add(
            EmbeddingTable(name="fast_embed", spec=dict(fast_embed), default=True)
        )
        session.commit()
        report = sync_presets(EmbeddingTable, presets, session=session)

    assert report["pruned"] == ["openai"]
    assert report["seeded"] == []
    with Session(engine) as session:
        rows = {row.name: row for row in session.query(EmbeddingTable).all()}
    assert set(rows) == {"fast_embed"}, "only the model that can run remains"
    assert rows["fast_embed"].default is True


def test_embedding_manager_syncs_presets_on_startup(monkeypatch):
    """The embedding manager must call the same reconciliation as the LLM one.

    A copy of the old code only seeded when the table was empty, so the vendor
    templates already in ``embedding`` survived every restart. The wiring is what
    this test pins; the rule itself is covered above.
    """
    from theflow.settings import settings as flowsettings

    import ktem.embeddings.manager as manager_mod

    calls: list[tuple] = []

    def fake_sync(table, presets, **kwargs):
        calls.append((table, presets))
        return {"seeded": [], "pruned": []}

    monkeypatch.setattr(manager_mod, "sync_presets", fake_sync)
    manager_mod.EmbeddingManager()

    assert calls, "the embedding pool is reconciled on startup"
    table, presets = calls[0]
    assert table is manager_mod.EmbeddingTable
    assert presets == flowsettings.KH_EMBEDDINGS
