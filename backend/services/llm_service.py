import json
import os
import re
from google import genai
from services.arxiv_service import ArxivPaper

MODEL_NAME = "gemini-3.1-flash-lite"


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> str:
    """LLMレスポンスからJSONブロックを抽出する。"""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


async def summarize_papers(
    papers: list[ArxivPaper],
) -> dict[str, str]:
    """
    論文の日本語要約生成。
    {arxiv_id: summary_ja} の dict を返す。
    """
    client = _get_client()

    papers_text = "\n\n".join(
        f"ID:{p.arxiv_id}\nTitle: {p.title}\nAuthors: {', '.join(p.authors)}\nAbstract: {p.abstract}"
        for p in papers
    )

    prompt = f"""あなたはリサーチアシスタントです。以下の論文それぞれについて、日本語要約（200字程度）を生成してください。

## 論文リスト
{papers_text}

## 出力形式
以下のJSON形式で出力してください（コードブロックで囲む）:
```json
{{
  "arxiv_id": "日本語要約（200字程度）",
  ...
}}
```"""

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    raw = _extract_json(response.text)

    try:
        summaries: dict[str, str] = json.loads(raw)
    except json.JSONDecodeError:
        summaries = {p.arxiv_id: "" for p in papers}

    return summaries
