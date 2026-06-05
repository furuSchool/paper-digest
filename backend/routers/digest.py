import logging
import os
import random
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import DeliveredPaper, Source, SourceInterest
from schemas import DigestResult, PaperSummary
from services import (
    arxiv_service,
    llm_service,
    docs_service,
    gmail_service,
    auth_service,
)
from services import semantic_scholar_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/digest", tags=["digest"])

_MOCK_PAPERS: list[PaperSummary] = [
    PaperSummary(
        arxiv_id="2406.00001",
        title="Scaling Laws for Neural Language Models: A Comprehensive Survey",
        authors=["Alice Smith", "Bob Johnson", "Carol Williams"],
        abstract="We present a comprehensive survey of scaling laws for neural language models, examining how model performance varies with compute budget, dataset size, and model parameters. Our analysis covers models ranging from 1M to 100B parameters and provides unified empirical laws across architectures.",
        url="https://arxiv.org/abs/2406.00001",
        summary_ja="大規模言語モデルのスケーリング則を体系的にまとめたサーベイ論文。パラメータ数・データセット・計算量の関係を1M〜100Bパラメータの範囲で実証的に分析し、アーキテクチャを横断した統一的な経験則を導出している。LLM開発の設計指針として有用。",
        matched_by_keyword=True,
    ),
    PaperSummary(
        arxiv_id="2406.00002",
        title="Efficient Attention Mechanisms for Long-Context Transformers",
        authors=["David Lee", "Eva Martinez"],
        abstract="This paper proposes a novel sparse attention mechanism that reduces the quadratic complexity of self-attention to linear, enabling transformers to process sequences of up to 1M tokens without memory overflow. We demonstrate state-of-the-art results on long-document summarization benchmarks.",
        url="https://arxiv.org/abs/2406.00002",
        summary_ja="Transformerのself-attentionを二次計算量から線形計算量に削減するスパースアテンション機構を提案。最大100万トークンの系列を処理可能にし、長文書要約ベンチマークでSOTAを達成。長文コンテキスト処理の実用化に向けた重要な進展。",
        matched_by_keyword=True,
    ),
    PaperSummary(
        arxiv_id="2406.00003",
        title="Reinforcement Learning from Human Feedback: Challenges and Opportunities",
        authors=["Frank Zhang", "Grace Kim", "Henry Brown"],
        abstract="We analyze the theoretical and practical challenges of RLHF for aligning large language models with human preferences. We identify reward hacking, distribution shift, and annotation inconsistency as primary failure modes, and propose mitigation strategies including constitutional AI and debate-based feedback.",
        url="https://arxiv.org/abs/2406.00003",
        summary_ja="大規模言語モデルのアライメント手法RLHFの課題と可能性を理論・実践の両面から分析。報酬ハッキング・分布シフト・アノテーションの不整合を主要な失敗モードとして特定し、Constitutional AIやディベートベースのフィードバックによる対策を提案。",
        matched_by_keyword=False,
    ),
]


async def _run_digest(
    source_id: int, db: AsyncSession, send: bool, use_mock: bool = False
) -> DigestResult:
    """ダイジェスト生成パイプラインの共通処理。"""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    interest_result = await db.execute(
        select(SourceInterest).where(SourceInterest.source_id == source_id)
    )
    interest = interest_result.scalars().first()

    categories = [
        c.strip()
        for c in (interest.arxiv_categories if interest else "").split(",")
        if c.strip()
    ]
    keywords = [
        k.strip()
        for k in (interest.keywords if interest else "").split(",")
        if k.strip()
    ]

    # モックモード
    if use_mock:
        logger.info(
            "[MOCK] arXiv fetch・LLM をスキップし、モックデータ %d件を使用",
            len(_MOCK_PAPERS),
        )
        paper_summaries = _MOCK_PAPERS
        doc_url: str | None = None

        if send:
            creds = await auth_service.get_credentials(db)
            if not creds:
                raise HTTPException(status_code=401, detail="Google not authenticated")

            doc_url = await docs_service.create_doc(
                creds=creds,
                description=source.description,
                papers=paper_summaries,
                folder_id=source.google_drive_folder_id,
            )
            await gmail_service.send_digest_email(
                creds=creds,
                to=source.email_to,
                name=source.name,
                papers=paper_summaries,
                doc_url=doc_url,
            )

        return DigestResult(
            source_id=source_id, papers=paper_summaries, doc_url=doc_url
        )

    if not categories and not source.citation_filter_enabled:
        raise HTTPException(
            status_code=400, detail="No arXiv categories configured for this source"
        )

    delivered_ids: set[str] = set()
    if source.dedup_enabled:
        delivered_result = await db.execute(
            select(DeliveredPaper.arxiv_id).where(DeliveredPaper.source_id == source_id)
        )
        delivered_ids = set(delivered_result.scalars().all())
        logger.info("配信済みID数: %d件", len(delivered_ids))

    selected: list[arxiv_service.ArxivPaper] = []
    citation_counts: dict[str, int] = {}
    use_citation_path = source.citation_filter_enabled and bool(keywords)

    if use_citation_path:
        pool_size = source.max_results * source.citation_top_multiplier
        logger.info(
            "[1/2] Semantic Scholar 検索開始 (keywords=%s, pool=%d)",
            keywords,
            pool_size,
        )
        t0 = time.perf_counter()
        try:
            citation_pairs = await semantic_scholar_service.search_by_citation(
                keywords=keywords,
                limit=pool_size,
                period_days=source.period,
            )
            logger.info(
                "[1/2] Semantic Scholar 完了: %.1f秒 → %d件",
                time.perf_counter() - t0,
                len(citation_pairs),
            )

            # dedup
            if source.dedup_enabled and delivered_ids:
                citation_pairs = [
                    (aid, cnt)
                    for aid, cnt in citation_pairs
                    if aid not in delivered_ids
                ]

            # sample
            if len(citation_pairs) > source.max_results:
                citation_pairs = random.sample(citation_pairs, source.max_results)

            citation_counts = {aid: cnt for aid, cnt in citation_pairs}
            arxiv_ids = [aid for aid, _ in citation_pairs]

            if arxiv_ids:
                logger.info("[1.5/2] arXiv fetch by IDs (%d件)", len(arxiv_ids))
                selected = await arxiv_service.fetch_papers_by_ids(arxiv_ids)
            else:
                selected = []

        except Exception as e:
            raise HTTPException(status_code=400, detail="Citation filter error")

    if not use_citation_path:
        if not categories:
            raise HTTPException(
                status_code=400, detail="No arXiv categories configured for this source"
            )
        logger.info(
            "[1/2] arXiv fetch 開始 (categories=%s, period=%d日)",
            categories,
            source.period,
        )
        t0 = time.perf_counter()
        all_papers = await arxiv_service.fetch_papers(
            categories=categories,
            period_days=source.period,
            keywords=keywords,
        )
        logger.info(
            "[1/2] arXiv fetch 完了: %.1f秒 → %d件",
            time.perf_counter() - t0,
            len(all_papers),
        )

        # dedup
        if source.dedup_enabled and delivered_ids:
            all_papers = [p for p in all_papers if p.arxiv_id not in delivered_ids]

        # sample
        if len(all_papers) <= source.max_results:
            selected = all_papers
        else:
            selected = random.sample(all_papers, source.max_results)

    if not selected:
        return DigestResult(source_id=source_id, papers=[], doc_url=None)

    logger.info("[2/2] LLM 要約開始 (%d件)", len(selected))
    t2 = time.perf_counter()
    summaries = await llm_service.summarize_papers(
        papers=selected,
        extra_prompt=source.llm_prompt or None,
    )
    logger.info("[2/2] LLM 要約完了: %.1f秒", time.perf_counter() - t2)

    paper_summaries = [
        PaperSummary(
            arxiv_id=p.arxiv_id,
            title=p.title,
            authors=p.authors,
            abstract=p.abstract,
            url=p.url,
            summary_ja=summaries.get(p.arxiv_id, ""),
            matched_by_keyword=p.matched_by_keyword,
            citation_count=citation_counts.get(p.arxiv_id),
        )
        for p in selected
    ]

    doc_url = None

    if send:
        creds = await auth_service.get_credentials(db)
        if not creds:
            raise HTTPException(status_code=401, detail="Google not authenticated")

        doc_url = await docs_service.create_doc(
            creds=creds,
            description=source.description,
            papers=paper_summaries,
            folder_id=source.google_drive_folder_id,
        )
        await gmail_service.send_digest_email(
            creds=creds,
            to=source.email_to,
            name=source.name,
            papers=paper_summaries,
            doc_url=doc_url,
        )

        if source.dedup_enabled:
            now = datetime.now(timezone.utc)
            for ps in paper_summaries:
                await db.execute(
                    text(
                        "INSERT INTO delivered_papers "
                        "(source_id, arxiv_id, delivered_at) VALUES (:sid, :aid, :dt) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"sid": source_id, "aid": ps.arxiv_id, "dt": now},
                )
            await db.commit()

    return DigestResult(source_id=source_id, papers=paper_summaries, doc_url=doc_url)


@router.post("/preview/{source_id}", response_model=DigestResult)
async def preview_digest(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    use_mock: bool = Query(
        default=False,
        description="Gemini APIコールをスキップしてモックデータを使用する",
    ),
) -> DigestResult:
    """プレビュー用（Docs書き込み・メール送信なし）。use_mock=true でLLMをバイパス。"""
    return await _run_digest(source_id, db, send=False, use_mock=use_mock)


@router.post("/run/{source_id}", response_model=DigestResult)
async def run_digest(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    use_mock: bool = Query(
        default=False,
        description="Gemini APIコールをスキップしてモックデータを使用する",
    ),
) -> DigestResult:
    """フル実行（Docs書き込み・メール送信あり）。use_mock=true でLLMをバイパス。"""
    return await _run_digest(source_id, db, send=True, use_mock=use_mock)


@router.post("/trigger")
async def trigger_digest(
    x_api_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    GitHub Actionsから呼ばれる。現在時刻（UTC HH:MM）と一致する有効ソースを全実行。
    TRIGGER_API_KEY で保護。
    """
    expected_key = os.getenv("TRIGGER_API_KEY", "")
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    now_utc = datetime.now(timezone.utc)
    current_time = now_utc.strftime("%H:%M")

    result = await db.execute(
        select(Source).where(
            Source.enabled == True, Source.schedule_time == current_time
        )  # noqa: E712
    )
    sources = result.scalars().all()

    executed: list[int] = []
    errors: list[dict] = []

    for source in sources:
        try:
            await _run_digest(source.id, db, send=True)
            executed.append(source.id)
        except Exception as e:
            errors.append({"source_id": source.id, "error": str(e)})

    return {
        "triggered_at": now_utc.isoformat(),
        "executed": executed,
        "errors": errors,
    }
