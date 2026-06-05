# パーソナル・リサーチダイジェストツール

## プロジェクト概要

arXivの最新論文を自動収集・LLMフィルタリングし、Google Docsにまとめ、GmailでDoc URLを通知する個人用ツール。

- **フロントエンド**: React + TypeScript + Vite（`/frontend`）
- **バックエンド**: Python 3.11+ + FastAPI（`/backend`）
- **DB**: SQLite + SQLAlchemy
- **LLM**: Gemini API（`gemini-3-flash-preview`）
- **定期実行**: GitHub Actions（cron）
- **デプロイ**: Render 無料枠

要件定義の全体は `docs/requirements.md` を参照。

---

## ディレクトリ構成

```
/
├── frontend/
│   ├── src/
│   │   ├── pages/          # Dashboard, SourceForm, DigestPreview, Settings
│   │   ├── components/
│   │   ├── api/            # バックエンドAPI呼び出し
│   │   └── utils/timezone.ts  # JST/UTC変換
│   └── vite.config.ts
├── backend/
│   ├── main.py
│   ├── routers/            # sources, digest, arxiv, auth
│   ├── services/           # arxiv, filter, llm, docs, gmail
│   ├── models.py           # SQLAlchemyモデル
│   ├── schemas.py          # Pydanticスキーマ
│   └── database.py
├── .github/workflows/digest.yml
├── docs/requirements.md
└── .env.example
```

---

## 開発ルール

### 全般
- コミットメッセージは日本語でOK
- 環境変数は必ず `.env.example` にも追記する（値は空にする）
- `.env` は絶対にコミットしない

### バックエンド（Python）
- 型ヒントを全関数に必ず付ける
- 非同期処理は `async/await` を使う（FastAPIの慣習に従う）
- エラーハンドリングは HTTPException を使う
- DBアクセスは全て SQLAlchemy 経由
- タイムゾーンは DB・処理系すべて UTC。`datetime.now(timezone.utc)` を使う
- `uv` を使う

### フロントエンド（TypeScript/React）
- `any` 型の使用禁止。必ず型定義する
- API呼び出しは `frontend/src/api/` 配下にまとめる
- 時刻表示はJST。`utils/timezone.ts` の変換関数を使う
- コンポーネントはfunctional component + hooks

### テスト
- バックエンド: pytest
- 主要なサービス関数（arxiv_service, llm_service）には最低限のユニットテストを書く

---

## よく使うコマンド

### バックエンド
```bash
cd backend
uv init
uv add
uv run uvicorn main:app --reload --port 8000
uv run pytest
```

### フロントエンド
```bash
cd frontend
npm install
npm run dev
npm run build
npm run typecheck
```

### DB初期化
```bash
cd backend
python -c "from database import init_db; init_db()"
```

---

## 環境変数（.env）

```
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
TRIGGER_API_KEY=
DATABASE_URL=sqlite:///./app.db
FRONTEND_URL=http://localhost:5173
```

---

## 注意事項・既知の制約

- Render無料枠はスリープするため、スケジューラーはGitHub Actions側で管理する（バックエンドにAPSchedulerは不要）
- Google OAuth2は初回セットアップ時に手動でブラウザ認証が必要。`/auth/google` エンドポイントで実施
- arXiv APIはレートリミットあり。1リクエスト/3秒を守ること
- Gemini APIコールは1ダイジェスト生成につき最大2回（スコアリング1回 + 要約1回）に抑える
- 配信時刻は **毎朝 07:00 JST (= 22:00 UTC) 固定**。ユーザーは頻度（何日ごと）のみ設定する
- 頻度チェックは `sources.last_triggered_at` と `schedule_frequency` で行う（`schedule_time` カラムは廃止）
- タイムゾーン: DB・バックエンドはすべてUTC。フロント表示のみJST変換

---

## 参考リンク

- [arXiv API ドキュメント](https://info.arxiv.org/help/api/index.html)
- [Gemini API ドキュメント](https://ai.google.dev/gemini-api/docs)
- [Google Docs API](https://developers.google.com/docs/api)
- [Gmail API](https://developers.google.com/gmail/api)
- [FastAPI ドキュメント](https://fastapi.tiangolo.com/)
