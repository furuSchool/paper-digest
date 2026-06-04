from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pytest
from services.arxiv_service import _build_query, fetch_papers, ArxivPaper


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
async def test_fetch_papers_returns_up_to_max_results():
    mock_results = [_make_arxiv_result(f"2406.0000{i}", f"Paper {i}") for i in range(10)]

    mock_client = MagicMock()
    mock_client.results.return_value = iter(mock_results)

    with patch("services.arxiv_service.arxiv.Client", return_value=mock_client):
        papers = await fetch_papers(
            categories=["cs.AI"],
            period_days=7,
            max_results=5,
            keywords=["diffusion"],
        )

    assert len(papers) <= 5


@pytest.mark.asyncio
async def test_fetch_papers_sets_matched_by_keyword_true():
    mock_results = [_make_arxiv_result("2406.00001", "Diffusion Model")]

    mock_client = MagicMock()
    mock_client.results.return_value = iter(mock_results)

    with patch("services.arxiv_service.arxiv.Client", return_value=mock_client):
        papers = await fetch_papers(
            categories=["cs.AI"],
            period_days=7,
            max_results=5,
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
            max_results=5,
            keywords=[],
        )

    assert all(p.matched_by_keyword is False for p in papers)
