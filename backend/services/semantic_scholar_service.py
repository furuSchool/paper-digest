import logging
import os
from datetime import datetime, timedelta, timezone
import httpx

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
SS_TIMEOUT_SEC = 30
SS_PAGE_SIZE = 100

logger = logging.getLogger(__name__)


def _get_headers() -> dict[str, str]:
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    if api_key:
        return {"x-api-key": api_key}
    return {}


def _year_range(period_days: int) -> str:
    """period_days から Semantic Scholar の year パラメータ用文字列を生成する。"""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=period_days)
    start_year = start.year
    end_year = today.year
    if start_year == end_year:
        return str(end_year)
    return f"{start_year}-{end_year}"


async def search_by_citation(
    keywords: list[str],
    limit: int,
    period_days: int,
) -> list[tuple[str, int]]:
    """
    キーワードで Semantic Scholar を検索し、引用数降順で上位 limit 件の
    (arxiv_id, citation_count) リストを返す。
    arXiv に存在しない論文（externalIds.ArXiv が null）は除外する。
    エラー・タイムアウト時は RuntimeError を送出する（呼び出し側でフォールバック）。
    """
    if not keywords:
        return []

    query = " OR ".join(
        f'"{kw.strip()}"' if " " in kw.strip() else kw.strip()
        for kw in keywords
        if kw.strip()
    )
    if not query:
        return []

    year = _year_range(period_days)
    headers = _get_headers()
    results: list[tuple[str, int]] = []
    token: str | None = None
    max_fetch = limit * 3  # arXiv論文のみ残すため多めに取得

    async with httpx.AsyncClient(timeout=SS_TIMEOUT_SEC) as client:
        fetched_total = 0
        while len(results) < limit and fetched_total < max_fetch:
            params: dict[str, object] = {
                "query": query,
                "fields": "citationCount,externalIds",
                "sort": "citationCount:desc",
                "year": year,
                "limit": SS_PAGE_SIZE,
            }
            if token:
                params["token"] = token

            resp = await client.get(
                f"{SEMANTIC_SCHOLAR_BASE}/paper/search/bulk",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            page_data = data.get("data", [])
            fetched_total += len(page_data)

            for paper in page_data:
                external_ids = paper.get("externalIds") or {}
                arxiv_id = external_ids.get("ArXiv")
                if not arxiv_id:
                    continue
                citation_count = paper.get("citationCount") or 0
                results.append((arxiv_id, citation_count))
                if len(results) >= limit:
                    break

            token = data.get("token")
            if not token:
                break

    logger.info(
        "Semantic Scholar: %d件取得 (arXiv論文のみ、year=%s)", len(results), year
    )
    return results[:limit]
