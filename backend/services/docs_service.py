from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from schemas import PaperSummary


def _build_doc_body(papers: list[PaperSummary]) -> tuple[list[dict], list[dict]]:
    """
    Google Docs API 用のリクエストリストを構築する。
    insertText / updateParagraphStyle と updateTextStyle(link) を分けて返す。
    link は insertText と同一 batchUpdate に含めると適用されないため分離する。
    """
    insert_requests: list[dict] = []
    link_requests: list[dict] = []
    cursor = 1  # 挿入位置（1-indexed）

    def insert(text: str, style: str | None = None) -> None:
        nonlocal cursor
        insert_requests.append(
            {
                "insertText": {
                    "location": {"index": cursor},
                    "text": text,
                }
            }
        )
        end = cursor + len(text)
        if style:
            insert_requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": cursor, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": style},
                        "fields": "namedStyleType",
                    }
                }
            )
        cursor = end

    for i, paper in enumerate(papers, 1):
        title_text = f"[{i}] {paper.title}\n"
        title_start = cursor
        insert(title_text, "HEADING_3")
        title_end = cursor - 1  # 末尾の \n を除く
        # リンクは insertText と別の batchUpdate で適用する必要がある
        link_requests.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": title_start, "endIndex": title_end},
                    "textStyle": {"link": {"url": paper.url}},
                    "fields": "link",
                }
            }
        )
        insert(f"Authors: {', '.join(paper.authors)}\n")
        if paper.citation_count is not None:
            insert(f"引用数: {paper.citation_count}\n")
        insert(f"\n{paper.summary_ja}\n")

    return insert_requests, link_requests


async def create_doc(
    creds: Credentials,
    description: str,
    papers: list[PaperSummary],
    folder_id: str | None,
) -> str:
    """Google Docs に新規ドキュメントを作成し、URL を返す。"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    doc_title = f"【{date_str}】{description}"

    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # ドキュメント作成
    doc = docs_service.documents().create(body={"title": doc_title}).execute()
    doc_id: str = doc["documentId"]

    insert_requests, link_requests = _build_doc_body(papers)

    # ① テキスト挿入・段落スタイル（1回目）
    if insert_requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": insert_requests},
        ).execute()

    # ② ハイパーリンク適用（2回目）— insertText と同一バッチに含めると無効になる
    if link_requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": link_requests},
        ).execute()

    # フォルダへ移動
    if folder_id:
        file_meta = drive_service.files().get(fileId=doc_id, fields="parents").execute()
        current_parents = ",".join(file_meta.get("parents", []))
        drive_service.files().update(
            fileId=doc_id,
            addParents=folder_id,
            removeParents=current_parents,
            fields="id, parents",
        ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"
