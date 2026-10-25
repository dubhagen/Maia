"""Keyword-only memory retrieval must not discard ordinary Unicode words."""

import asyncio

import pytest

from agent.memory.config import MemoryConfig
from agent.memory.manager import MemoryManager
from agent.memory.storage import MemoryChunk


@pytest.mark.parametrize("query", ["caf\u00e9", "na\u00efve", "r\u00e9sum\u00e9", "\u00e9t\u00e9", "invoice", "fa\u00e7ade"])
@pytest.mark.parametrize("fts_available", [True, False])
def test_keyword_only_manager_finds_unicode_memory(tmp_path, query, fts_available):
    manager = MemoryManager(MemoryConfig(workspace_root=str(tmp_path), sync_on_search=False))
    try:
        if fts_available and not manager.storage.fts5_available:
            pytest.skip("SQLite has no FTS5")
        if not fts_available:
            manager.storage.fts5_available = False
            manager.storage.trigram_fts5_available = False
        manager.storage.save_chunk(MemoryChunk(
            id="note", user_id=None, scope="shared", source="memory", path="memory/note.md",
            start_line=1, end_line=1, text=f"{query}: details to remember", embedding=None, hash="note-hash",
        ))
        results = asyncio.run(manager.search(query))
        assert [result.path for result in results] == ["memory/note.md"]
        assert asyncio.run(manager.search("unrelatedword")) == []
    finally:
        manager.storage.close()


def test_trigram_query_keeps_one_unicode_term_beside_another(tmp_path):
    manager = MemoryManager(MemoryConfig(workspace_root=str(tmp_path), sync_on_search=False))
    try:
        if not manager.storage.trigram_fts5_available:
            pytest.skip("SQLite has no trigram FTS5")
        # Glued together so unicode61 does not treat the shared prefix as its own
        # word. Trigram search then has to keep both terms (the decoy has only the first).
        for name, text in [("match", "caf\u00e9na\u00efve"), ("decoy", "caf\u00e9unrelated")]:
            manager.storage.save_chunk(MemoryChunk(
                id=name, user_id=None, scope="shared", source="memory", path=f"memory/{name}.md",
                start_line=1, end_line=1, text=text, embedding=None, hash=name,
            ))
        results = asyncio.run(manager.search("caf\u00e9 na\u00efve"))
        assert [result.path for result in results] == ["memory/match.md"]
    finally:
        manager.storage.close()
