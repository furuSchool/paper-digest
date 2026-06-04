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
    extra_prompt: str | None = None,
) -> dict[str, str]:
    """
    論文の日本語要約生成。
    {arxiv_id: summary_ja} の dict を返す。
    extra_prompt が設定されている場合、基本プロンプトの末尾に追記する。
    """
    client = _get_client()

    papers_text = "\n\n".join(
        f"ID:{p.arxiv_id}\nTitle: {p.title}\nAuthors: {', '.join(p.authors)}\nAbstract: {p.abstract}"
        for p in papers
    )

    extra_section = f"\n\n## 追加指示\n{extra_prompt}" if extra_prompt else ""

    prompt = f"""以下の論文それぞれについて、以下の条件に従って日本語要約を生成してください。

## 日本語要約の要件
- 要約には、Abstract の記述に忠実であることを最優先する
- 第1文: 「本研究は、[対象としているタスク]に対して、[手法]を提案し、[結果]がわかった。」
- その後、以下の項目がわかる形で要約を作成する。
    - 対象としている状況/タスクが何か。入出力関係はどのようなものか。
    - 提案した具体的な手法。
    - 主な結果とその考察
- キーワードや専門用語は日本語だけでなく、英語による表現を括弧にて記述

## 論文リスト
{papers_text}

## 出力形式
以下のJSON形式で出力してください（コードブロックで囲む）:
```json
{{
  "arxiv_id": "日本語要約",
  ...
}}
```{extra_section}"""

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
