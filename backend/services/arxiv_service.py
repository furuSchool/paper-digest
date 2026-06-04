import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import arxiv
import httpx

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


def _normalize_arxiv_id(arxiv_id: str) -> str:
    """バージョンサフィックスを除去する: '2406.00001v2' → '2406.00001'"""
    return re.sub(r'v\d+$', '', arxiv_id)


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


def _make_arxiv_paper(result: arxiv.Result, matched_by_keyword: bool) -> ArxivPaper:
    published = result.published
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return ArxivPaper(
        arxiv_id=_normalize_arxiv_id(result.get_short_id()),
        title=result.title,
        authors=[a.name for a in result.authors],
        abstract=result.summary,
        url=result.entry_id,
        published=published,
        categories=result.categories,
        matched_by_keyword=matched_by_keyword,
    )


async def fetch_papers(
    categories: list[str],
    period_days: int,
    keywords: list[str],
) -> list[ArxivPaper]:
    """
    period_days 日分の日付範囲を1クエリでカバーし、MAX_PAPERS_PER_QUERY 件を上限に取得して返す。
    サンプリングは呼び出し側（digest.py）で行う。
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
        return [_make_arxiv_paper(r, matched_by_keyword) for r in client.results(search)]

    loop = asyncio.get_running_loop()
    try:
        papers = await asyncio.wait_for(
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

    return papers


_ARXIV_ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _parse_atom_entry(entry: ET.Element, matched_by_keyword: bool) -> ArxivPaper:
    ns = _ARXIV_ATOM_NS

    raw_id = entry.findtext("atom:id", default="", namespaces=ns)
    arxiv_id = _normalize_arxiv_id(raw_id.split("/abs/")[-1])

    title_el = entry.find("atom:title", ns)
    title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""

    summary_el = entry.find("atom:summary", ns)
    abstract = (summary_el.text or "").strip() if summary_el is not None else ""

    published_el = entry.find("atom:published", ns)
    try:
        published = datetime.fromisoformat(
            (published_el.text or "").replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        published = datetime.now(timezone.utc)

    authors = [
        (a.findtext("atom:name", default="", namespaces=ns) or "")
        for a in entry.findall("atom:author", ns)
    ]

    categories = [
        t.get("term", "")
        for t in entry.findall("atom:category", ns)
        if t.get("term")
    ]

    url = f"https://arxiv.org/abs/{arxiv_id}"
    for link in entry.findall("atom:link", ns):
        if link.get("rel") == "alternate":
            url = link.get("href", url)
            break

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        published=published,
        categories=categories,
        matched_by_keyword=matched_by_keyword,
    )


async def fetch_papers_by_ids(
    arxiv_ids: list[str],
    matched_by_keyword: bool = True,
) -> list[ArxivPaper]:
    """arxiv ID リストを指定して論文詳細を取得する（引用数フィルタパス用）。

    arxiv ライブラリの Search(id_list=...) は search_query= や sort パラメータを
    付加してしまい 0 件になる場合があるため、arXiv API に直接リクエストする。
    URL 例: /api/query?id_list=2503.01774,2502.13144&start=0&max_results=100
    """
    if not arxiv_ids:
        return []

    async with httpx.AsyncClient(timeout=ARXIV_TIMEOUT_SEC) as http_client:
        resp = await http_client.get(
            "https://export.arxiv.org/api/query",
            params={
                "id_list": ",".join(arxiv_ids),
                "start": 0,
                "max_results": len(arxiv_ids),
            },
        )
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    papers = [
        _parse_atom_entry(entry, matched_by_keyword)
        for entry in root.findall("atom:entry", _ARXIV_ATOM_NS)
    ]
    return papers
