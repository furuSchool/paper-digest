from unittest.mock import AsyncMock, MagicMock, patch
from services.llm_service import _extract_json, summarize_papers
from services.arxiv_service import ArxivPaper
from datetime import datetime, timezone

SAMPLE_PAPERS = [
    ArxivPaper(
        arxiv_id="2401.00001",
        title="Deep Learning for NLP",
        abstract="We propose a new method for natural language processing.",
        authors=["Alice Smith"],
        url="https://arxiv.org/abs/2401.00001",
        published=datetime(2024, 1, 15, tzinfo=timezone.utc),
        categories=["cs.CL", "cs.LG"],
    ),
    ArxivPaper(
        arxiv_id="2401.00002",
        title="Reinforcement Learning Survey",
        abstract="A comprehensive survey of reinforcement learning methods.",
        authors=["Bob Jones"],
        url="https://arxiv.org/abs/2401.00002",
        published=datetime(2024, 1, 16, tzinfo=timezone.utc),
        categories=["cs.LG"],
    ),
]


def _make_mock_client(response_text: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    return mock_client


def test_extract_json_with_code_block():
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_without_code_block():
    text = '{"key": "value"}'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_plain_code_block():
    text = "```\n{\"key\": \"value\"}\n```"
    assert _extract_json(text) == '{"key": "value"}'


async def test_summarize_papers_returns_summaries():
    summary_json = '```json\n{"2401.00001": "深層学習を用いた自然言語処理の新手法を提案。", "2401.00002": "強化学習手法の包括的サーベイ。"}\n```'
    mock_client = _make_mock_client(summary_json)

    with patch("services.llm_service._get_client", return_value=mock_client):
        summaries = await summarize_papers(
            papers=SAMPLE_PAPERS,
        )

    assert summaries["2401.00001"] == "深層学習を用いた自然言語処理の新手法を提案。"
    assert summaries["2401.00002"] == "強化学習手法の包括的サーベイ。"


async def test_summarize_papers_fallback_on_invalid_json():
    mock_client = _make_mock_client("not valid json")

    with patch("services.llm_service._get_client", return_value=mock_client):
        summaries = await summarize_papers(
            papers=SAMPLE_PAPERS,
        )

    # パース失敗時は全論文に空文字を返す
    assert summaries["2401.00001"] == ""
    assert summaries["2401.00002"] == ""
