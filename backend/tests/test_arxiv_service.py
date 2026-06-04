from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pytest
from services.arxiv_service import _build_query, _normalize_arxiv_id, fetch_papers, fetch_papers_by_ids, ArxivPaper


# --- _normalize_arxiv_id ---

def test_normalize_strips_version():
    assert _normalize_arxiv_id("2406.00001v2") == "2406.00001"

def test_normalize_no_version():
    assert _normalize_arxiv_id("2406.00001") == "2406.00001"

def test_normalize_old_style():
    assert _normalize_arxiv_id("cs/0510013v3") == "cs/0510013"


# --- _build_query ---

def test_build_query_with_keywords():
    q = _build_query(["cs.AI", "cs.LG"], ["diffusion", "transformer"], "20260525", "20260601")
    assert "cat:cs.AI OR cat:cs.LG" in q
    assert "ti:diffusion OR abs:diffusion" in q
    assert "ti:transformer OR abs:transformer" in q
    assert "submittedDate:[202605250000 TO 202606012359]" in q


def test_build_query_without_keywords():
    q = _build_query(["cs.AI"], [], "20260525", "20260601")
    assert "cat:cs.AI" in q
    assert "submittedDate:[202605250000 TO 202606012359]" in q
    assert "ti:" not in q
    assert "abs:" not in q


# --- fetch_papers ---

def _make_arxiv_result(arxiv_id: str, title: str) -> MagicMock:
    result = MagicMock()
    result.get_short_id.return_value = arxiv_id
    result.title = title
    result.summary = "Abstract text."
    result.authors = []
    result.entry_id = f"https://arxiv.org/abs/{arxiv_id}"
    result.published = datetime(2026, 6, 1, tzinfo=timezone.utc)
    result.categories = ["cs.AI"]
    return result


@pytest.mark.asyncio
async def test_fetch_papers_returns_all_results():
    """fetch_papers はサンプリングせず、取得した全論文を返す。"""
    mock_results = [_make_arxiv_result(f"2406.0000{i}", f"Paper {i}") for i in range(10)]

    mock_client = MagicMock()
    mock_client.results.return_value = iter(mock_results)

    with patch("services.arxiv_service.arxiv.Client", return_value=mock_client):
        papers = await fetch_papers(
            categories=["cs.AI"],
            period_days=7,
            keywords=["diffusion"],
        )

    assert len(papers) == 10


@pytest.mark.asyncio
async def test_fetch_papers_sets_matched_by_keyword_true():
    mock_results = [_make_arxiv_result("2406.00001", "Diffusion Model")]

    mock_client = MagicMock()
    mock_client.results.return_value = iter(mock_results)

    with patch("services.arxiv_service.arxiv.Client", return_value=mock_client):
        papers = await fetch_papers(
            categories=["cs.AI"],
            period_days=7,
            keywords=["diffusion"],
        )

    assert all(p.matched_by_keyword is True for p in papers)


@pytest.mark.asyncio
async def test_fetch_papers_matched_by_keyword_false_when_no_keywords():
    mock_results = [_make_arxiv_result("2406.00001", "Some Paper")]

    mock_client = MagicMock()
    mock_client.results.return_value = iter(mock_results)

    with patch("services.arxiv_service.arxiv.Client", return_value=mock_client):
        papers = await fetch_papers(
            categories=["cs.AI"],
            period_days=7,
            keywords=[],
        )

    assert all(p.matched_by_keyword is False for p in papers)


# --- fetch_papers_by_ids ---

_ATOM_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2406.00001v1</id>
    <title>Some Paper</title>
    <summary>Abstract text.</summary>
    <published>2026-06-01T00:00:00Z</published>
    <author><name>Alice</name></author>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <link rel="alternate" href="https://arxiv.org/abs/2406.00001"/>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_fetch_papers_by_ids_returns_papers():
    from unittest.mock import AsyncMock
    import httpx

    mock_resp = MagicMock()
    mock_resp.text = _ATOM_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_resp)

    with patch("services.arxiv_service.httpx.AsyncClient", return_value=mock_http):
        papers = await fetch_papers_by_ids(["2406.00001"])

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2406.00001"
    assert papers[0].matched_by_keyword is True


@pytest.mark.asyncio
async def test_fetch_papers_by_ids_empty_returns_empty():
    papers = await fetch_papers_by_ids([])
    assert papers == []
