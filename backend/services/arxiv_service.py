import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import arxiv

MAX_PAPERS_PER_QUERY = 300  # 1クエリあたりの上限
ARXIV_TIMEOUT_SEC = 300  # この秒数を超えたら RuntimeError を送出


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    published: datetime
    categories: list[str]
    matched_by_keyword: bool = field(default=False)


def _build_query(
    categories: list[str], keywords: list[str], date_start: str, date_end: str
) -> str:
    """arXiv 検索クエリを組み立てる。日付範囲・キーワードは ti: / abs: フィールドで OR 検索。"""
    category_query = " OR ".join(f"cat:{c}" for c in categories)
    date_filter = f"submittedDate:[{date_start}0000 TO {date_end}2359]"

    if keywords:
        kw_clauses = [
            f"(ti:{kw.strip()} OR abs:{kw.strip()})" for kw in keywords if kw.strip()
        ]
        keyword_query = " OR ".join(kw_clauses)
        return f"({category_query}) AND ({keyword_query}) AND {date_filter}"

    return f"({category_query}) AND {date_filter}"


async def fetch_papers(
    categories: list[str],
    period_days: int,
    max_results: int,
    keywords: list[str],
) -> list[ArxivPaper]:
    """
    period_days 日分の日付範囲を1クエリでカバーし、
    MAX_PAPERS_PER_QUERY 件を上限に取得後、max_results 件にランダムサンプリングして返す。
    """
    today = datetime.now(timezone.utc).date()
    end_date = today - timedelta(days=1)
    start_date = today - timedelta(days=period_days)

    query = _build_query(
        categories,
        keywords,
        start_date.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
    )
    matched_by_keyword = bool(keywords)

    search = arxiv.Search(
        query=query,
        max_results=MAX_PAPERS_PER_QUERY,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=0)

    def _fetch() -> list[ArxivPaper]:
        papers = []
        for result in client.results(search):
            published = result.published
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            papers.append(
                ArxivPaper(
                    arxiv_id=result.get_short_id(),
                    title=result.title,
                    authors=[a.name for a in result.authors],
                    abstract=result.summary,
                    url=result.entry_id,
                    published=published,
                    categories=result.categories,
                    matched_by_keyword=matched_by_keyword,
                )
            )
        return papers

    loop = asyncio.get_running_loop()
    try:
        all_papers = await asyncio.wait_for(
            loop.run_in_executor(None, _fetch),
            timeout=ARXIV_TIMEOUT_SEC,
        )
    except TimeoutError:
        raise RuntimeError(
            f"arXiv API が {ARXIV_TIMEOUT_SEC} 秒以内に応答しませんでした"
        )
    except arxiv.HTTPError as e:
        if e.status == 429:
            return []
        raise RuntimeError(f"arXiv API エラー (HTTP {e.status}): {e}") from e

    if len(all_papers) <= max_results:
        return all_papers
    return random.sample(all_papers, max_results)
