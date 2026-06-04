from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx
from services.semantic_scholar_service import search_by_citation


def _make_mock_response(data: list[dict], token: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": data, "token": token}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_search_by_citation_returns_arxiv_papers():
    page = [
        {"citationCount": 100, "externalIds": {"ArXiv": "2406.00001"}},
        {"citationCount": 80,  "externalIds": {"ArXiv": None}},        # arXiv以外は除外
        {"citationCount": 60,  "externalIds": {"ArXiv": "2406.00002"}},
    ]
    mock_resp = _make_mock_response(page)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("services.semantic_scholar_service.httpx.AsyncClient", return_value=mock_client):
        results = await search_by_citation(keywords=["diffusion"], limit=5, period_days=365)

    assert len(results) == 2
    assert results[0] == ("2406.00001", 100)
    assert results[1] == ("2406.00002", 60)


@pytest.mark.asyncio
async def test_search_by_citation_respects_limit():
    page = [
        {"citationCount": 100, "externalIds": {"ArXiv": f"2406.0000{i}"}}
        for i in range(10)
    ]
    mock_resp = _make_mock_response(page)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("services.semantic_scholar_service.httpx.AsyncClient", return_value=mock_client):
        results = await search_by_citation(keywords=["diffusion"], limit=3, period_days=30)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_search_by_citation_empty_keywords():
    results = await search_by_citation(keywords=[], limit=5, period_days=7)
    assert results == []


@pytest.mark.asyncio
async def test_search_by_citation_http_error_raises():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=MagicMock()
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("services.semantic_scholar_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await search_by_citation(keywords=["llm"], limit=5, period_days=7)
