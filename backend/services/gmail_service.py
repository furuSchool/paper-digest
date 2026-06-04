import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from schemas import PaperSummary


def _build_email_body(papers: list[PaperSummary], doc_url: str) -> str:
    items = []
    for i, paper in enumerate(papers, 1):
        items.append(
            f'<li style="margin-bottom:12px;">'
            f'<a href="{paper.url}" style="font-weight:bold;">[{i}] {paper.title}</a><br>'
            f'<span style="color:#555;">{paper.summary_ja}</span>'
            f"</li>"
        )
    items_html = "\n".join(items)
    return f'<p><a href="{doc_url}">ドキュメント</a></p><ul>{items_html}</ul>'


async def send_digest_email(
    creds: Credentials,
    to: str,
    name: str,
    papers: list[PaperSummary],
    doc_url: str,
) -> None:
    """Gmail API でダイジェストメールを送信する。"""
    subject = f"【{name}】今日の論文"
    body = _build_email_body(papers, doc_url)

    message = MIMEText(body, "html", "utf-8")
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()
