## 1. システム概要

個人用リサーチダイジェストツール。arXivの最新論文を自動収集・キーワードフィルタリングし、LLMで日本語要約を生成。Google Docsにまとめ、GmailでDoc URLを通知する。React + FastAPIで構築し、フロントから全設定を管理できる。

### 目的

特定の自分にフィットした分野の最新情報を、概要だけすばやくチェックし、詳しく見たいものは元リンクへ飛べるようにする。

---

## 2. アーキテクチャ

```
[GitHub Actions]（定期実行 / cron）
  └── バックエンドの /digest/trigger をHTTPで叩く

[React Frontend @ Vercel]
  ↕ REST API（VITE_API_URL で向き先を切り替え）
[FastAPI Backend @ Render]
  ├── arXiv API（論文取得）
  ├── Semantic Scholar API（引用数フィルタリング）
  ├── Gemini API（要約生成のみ）
  ├── Google Docs API（ドキュメント作成・書き込み）
  └── Gmail API（メール送信）

[Neon PostgreSQL]（設定データ・配信済み論文IDを保存）
```

---

## 3. データモデル

### `sources`（配信ソース設定）

| カラム | 型 | 説明 |
| --- | --- | --- |
| id | INTEGER | PK |
| name | TEXT | 表示名 |
| description | TEXT | ダイジェストタイトルに使用する説明文 |
| enabled | BOOLEAN | 有効 / 無効 |
| schedule_frequency | INTEGER | `1` なら毎日、`7` なら週1回（日数で指定） |
| last_triggered_at | DATETIME | 最後にダイジェストを配信した日時（UTC）。NULL なら未配信 |
| email_to | TEXT | 配信先メールアドレス |
| max_results | INTEGER | 最終的に配信する論文件数 |
| period | INTEGER | 取得対象期間（日数。例: `7` なら過去7日） |
| google_drive_folder_id | TEXT | 配信ドキュメントを格納するDriveフォルダID（NULL の場合はルート） |
| created_at | DATETIME | UTC |

### `source_interests`（ソースごとの興味設定）

| カラム | 型 | 説明 |
| --- | --- | --- |
| id | INTEGER | PK |
| source_id | INTEGER | FK → sources.id |
| arxiv_categories | TEXT | `cs.LG,cs.CL` 等（カンマ区切り） |
| keywords | TEXT | `LLM agent, multimodal` 等（カンマ区切り）。arXiv APIの `ti:` / `abs:` フィールドでクエリに組み込む |

### `google_tokens`（Google OAuth2トークン）

| カラム | 型 | 説明 |
| --- | --- | --- |
| id | INTEGER | PK |
| access_token | TEXT |  |
| refresh_token | TEXT |  |
| token_expiry | DATETIME | UTC |
| updated_at | DATETIME | UTC |

---

## 4. フロントエンド画面構成

```
/                      ← ダッシュボード
/sources/new           ← ソース新規登録
/sources/:id           ← ソース編集
/digest/preview/:id    ← ダイジェストプレビュー（表示のみ・送信なし）
/settings              ← Google OAuth認証・フォルダ設定
```

### 各画面の詳細

### `/`（ダッシュボード）

- 登録済みソースの一覧カード表示
- 各ソースの有効/無効トグル
- 次回配信予定時刻（JSTで表示）
- 「今すぐプレビュー」ボタン → `/digest/preview/:id` へ遷移

### `/sources/new` と `/sources/:id`（ソース登録・編集）

入力項目：

| 項目 | UI部品 | 備考 |
| --- | --- | --- |
| 表示名 | テキスト入力 |  |
| 説明文 | テキスト入力 | ダイジェストタイトルに使用 |
| arXivカテゴリ | チェックボックス一覧 + カスタム入力 | プリセット9件 + 自由入力可（例: cs.LG） |
| キーワード | テキスト入力（カンマ区切り） | arXiv APIの `ti:` / `abs:` フィールドで絞り込み |
| 配信頻度 | セレクト（毎日 / 毎週） | 配信時刻は 07:00 JST 固定（変更不可） |
| 取得件数上限 | 数値入力 | 最終配信件数 |
| 取得期間（日） | 数値入力 | ランダムサンプリングの対象期間 |
| 配信先メール | テキスト入力 |  |
| Driveフォルダ | テキスト入力 | Google Drive フォルダID（任意） |
| 有効/無効 | チェックボックス |  |

### `/digest/preview/:id`（プレビュー）

- APIを再実行してダイジェスト内容を取得・表示
- Google Docs書き込み・Gmail送信は**行わない**
- `use_mock=true` クエリパラメータで arXiv/LLM をバイパスしてモックデータを使用可能
- ローディング中はスピナー表示（数十秒かかる場合あり）
- 論文カードを一覧表示（タイトル・著者・matched_by_keyword・アブストラクト・日本語要約・リンク）

### `/settings`

- Google OAuth2認証ボタン（初回のみ）
- 認証状態の表示（認証済み / 未認証）
- 認証リセット

---

## 5. バックエンドAPI

| Method | Path | 説明 |
| --- | --- | --- |
| GET | `/sources` | ソース一覧取得 |
| POST | `/sources` | ソース新規作成 |
| PUT | `/sources/:id` | ソース更新 |
| DELETE | `/sources/:id` | ソース削除 |
| POST | `/digest/run/:id` | ダイジェスト生成（Docs書き込み・メール送信あり） |
| POST | `/digest/preview/:id` | ダイジェスト生成（表示用・送信なし）。`?use_mock=true` でモード切替可 |
| POST | `/digest/trigger` | GitHub Actionsから毎日 22:00 UTC に呼ばれる。`schedule_frequency` 日以上未配信のソースを全実行 |
| GET | `/auth/google` | Google OAuth2認証開始 |
| GET | `/auth/google/callback` | OAuth2コールバック・トークン保存 |
| GET | `/auth/status` | 認証状態確認 |
| DELETE | `/auth/google` | 認証リセット |

---

## 6. 処理パイプライン（ダイジェスト生成）

```
① arXiv 論文取得（arxiv_service.fetch_papers）
   - period_days 日分をカバーする1クエリを発行（日付範囲指定）
   - arXiv API クエリ:
       キーワードあり: (cat:X OR cat:Y) AND (ti:kw OR abs:kw) AND submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]
       キーワードなし: (cat:X OR cat:Y) AND submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]
   - 最大 MAX_PAPERS_PER_QUERY(300) 件をページネーション取得（100件/ページ）
     ※ ページ間は delay_seconds=3 の待機
   - matched_by_keyword フラグ: キーワードあり → True、なし → False
   - 取得件数が max_results を超える場合はランダムサンプリングで絞る
   - タイムアウト: ARXIV_TIMEOUT_SEC(300) 秒

② LLM 要約生成（llm_service.summarize_papers）
   - Gemini API で各論文の日本語要約（200字程度）を一括生成（1回のAPIコール）
   - レスポンスは {arxiv_id: summary_ja} のJSONを期待

③ Google Docsに新規ドキュメント作成・書き込み
   - 指定 Drive フォルダに格納（フォルダID未設定の場合はルート）
   - タイトルはクリック可能リンクとして設定

④ Gmailで通知メール送信
   - Doc URLをHTMLメール本文に含める
   - 件名: 【{source.name}】今日の論文
```

---

## 7. 配信フォーマット

### Google Docs（1配信 = 新規ドキュメント）

```
タイトル: 【YYYY-MM-DD】<description>

[1] Title (English、原文まま)  ← クリックで arxiv.org へ
Authors: ...
[キーワード一致 / ランダム選択]
Abstract: ... (English、原文まま)
日本語要約: ...（200字程度）

[2] ...
```

### Gmail本文（HTML）

```
件名: 【{source.name}】今日の論文

Google Docsで読む: {Doc URL}

[1] Title (English)  ← <a href> リンク
Authors: ...
[キーワード一致 / ランダム選択]
Abstract: ...
日本語要約: ...

[2] ...
```

---

## 8. タイムゾーン方針

| 場所 | タイムゾーン |
| --- | --- |
| DBの保存値（`last_triggered_at` 等） | UTC |
| バックエンド処理・GitHub Actions | UTC |
| フロントの表示 | JST（UTC+9）に変換して表示 |
| 配信時刻 | 07:00 JST 固定（= 22:00 UTC）。ユーザー設定なし |

---

## 9. 定期実行（GitHub Actions）

```yaml
# .github/workflows/digest.yml

name: Run Digest
on:
  schedule:
    - cron: '0 22 * * *'  # 毎日 22:00 UTC (= 翌 07:00 JST) に実行
  workflow_dispatch:       # 手動実行も可

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Wake up backend
        run: |
          # Render 無料枠のコールドスタート対策: /health が 200 を返すまで最大 5 分ポーリング
          for i in $(seq 1 20); do
            STATUS=$(curl -o /dev/null -s -w "%{http_code}" "${{ secrets.BACKEND_URL }}/health")
            if [ "$STATUS" = "200" ]; then
              echo "Backend ready (attempt $i)"
              break
            fi
            echo "Attempt $i/20: got $STATUS, sleeping 15s..."
            sleep 15
          done
      - name: Trigger digest
        run: |
          curl -X POST \
            -H "X-API-Key: ${{ secrets.TRIGGER_API_KEY }}" \
            "${{ secrets.BACKEND_URL }}/digest/trigger" \
            --fail --silent --show-error
```

### 配信時刻の設計方針

- 配信時刻は **毎朝 07:00 JST (= 22:00 UTC)** に固定。ユーザーは変更不可
- GitHub Actions の cron は `0 22 * * *`（1日1回）に設定し、不要な Render 起動を排除する
- `/digest/trigger` は `schedule_frequency` 日以上未配信のソースのみを実行する（頻度チェック）
  - 毎日（`schedule_frequency=1`）: 毎日配信
  - 週1回（`schedule_frequency=7`）: 前回配信から7日以上経過した日のみ配信
- 配信実績は `sources.last_triggered_at`（UTC）に記録される
- `TRIGGER_API_KEY` による簡易認証でエンドポイントを保護する
- GitHub Actions の secrets に `BACKEND_URL`（例: `https://paper-digest.onrender.com`）を登録する

### Neon PostgreSQL への移行時のスキーマ変更

既存の Neon DB に対して以下の ALTER TABLE を手動で実行すること：

```sql
ALTER TABLE sources ADD COLUMN last_triggered_at TIMESTAMP WITH TIME ZONE;
```

（`schedule_time` カラムは廃止済み。DB に残っていても動作に影響はないが、不要なら `ALTER TABLE sources DROP COLUMN schedule_time;` で削除可）

---

## 10. Google OAuth2・外部API認証

| サービス | スコープ |
| --- | --- |
| Gmail API | `gmail.send` |
| Google Docs API | `documents` |
| Google Drive API | `drive.file`（作成したファイルのみ） |
- 3サービスを1つのOAuth2フローで認証（スコープをまとめる）
- access_token / refresh_token は `google_tokens` テーブルに保存
- 期限切れ時はrefresh_tokenで自動再取得

---

## 11. 技術スタック

| レイヤー | 技術 |
| --- | --- |
| フロントエンド | React + TypeScript + Vite |
| バックエンド | Python 3.11+ + FastAPI |
| DB | Neon (PostgreSQL) + SQLAlchemy + asyncpg（本番）/ SQLite + aiosqlite（ローカル開発） |
| LLM | Gemini API（`gemini-3.1-flash-lite`）※要約のみ |
| 外部API | arXiv API, Semantic Scholar API, Google Docs API, Gmail API, Google Drive API |
| 認証 | Google OAuth2（Docs + Gmail + Drive 一本化） |
| 定期実行 | GitHub Actions（cron） |
| フロントホスティング | Vercel（無料枠） |
| バックホスティング | Render Web Service（無料枠） |
| コールドスタート対策 | UptimeRobot（5分ごとに /health を監視、無料枠） |

---

## 12. 環境変数（`.env`）

### バックエンド（Render 環境変数）

```
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://<your-backend>.onrender.com/auth/google/callback
TRIGGER_API_KEY=
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
FRONTEND_URL=https://<your-app>.vercel.app
SEMANTIC_SCHOLAR_API_KEY=    # 任意。設定なしでも動作（レートリミットが低い）
```

### フロントエンド（Vercel 環境変数）

```
VITE_API_URL=https://<your-backend>.onrender.com
```

### ローカル開発（`.env`）

```
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
TRIGGER_API_KEY=
DATABASE_URL=sqlite:///./app.db    # ローカルのみ SQLite 使用
FRONTEND_URL=http://localhost:5173
SEMANTIC_SCHOLAR_API_KEY=
```

- フロントのローカル開発では `VITE_API_URL` を未設定にしておく → `/api` にフォールバックし Vite プロキシ経由でバックエンドと通信

---

## 13. ディレクトリ構成

```
/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── SourceForm.tsx
│   │   │   ├── DigestPreview.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   ├── api/           ← バックエンドAPI呼び出し
│   │   └── utils/
│   │       └── timezone.ts  ← JST/UTC変換
│   └── vite.config.ts
│
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── sources.py
│   │   ├── digest.py
│   │   ├── arxiv.py
│   │   └── auth.py
│   ├── services/
│   │   ├── arxiv_service.py      ← arXiv API取得（キーワードはAPIクエリに組み込み）
│   │   ├── llm_service.py        ← Gemini API要約生成
│   │   ├── docs_service.py       ← Google Docs書き込み
│   │   └── gmail_service.py      ← Gmail送信
│   ├── models.py                 ← SQLAlchemyモデル
│   ├── schemas.py                ← Pydanticスキーマ
│   └── database.py
│
├── .github/
│   └── workflows/
│       └── digest.yml
│
└── .env
```

---

## 14. デプロイ構成と手順

### 構成

| コンポーネント | サービス | 備考 |
| --- | --- | --- |
| フロントエンド | Vercel（無料） | GitHub から自動デプロイ |
| バックエンド | Render Web Service（無料） | `backend/` をルートとして設定 |
| DB | Neon PostgreSQL（無料） | `DATABASE_URL` として Render に設定 |
| コールドスタート対策 | UptimeRobot（無料） | 5分ごとに `/health` を HTTP 監視 |

### DB の選定理由（SQLite → Neon）

- Render 無料枠はファイルシステムが揮発性（デプロイ・再起動のたびにリセット）
- SQLite のファイルはそのたびに消えるため永続化不可
- Neon を選んだ理由：
  - サーバーレス PostgreSQL、無料枠 0.5GB
  - アイドル時は自動スケールダウン（課金なし）
  - SQLAlchemy + asyncpg で最小限のコード変更で移行可能

### CORS の対処方針

- バックエンドは `FRONTEND_URL` 環境変数を CORS の許可オリジンに使用（実装済み）
- Render の環境変数に `FRONTEND_URL=https://<your-app>.vercel.app` を設定する
- フロントエンドの `client.ts` は `VITE_API_URL` 環境変数でバックエンドURLを切り替え：
  - ローカル開発: `VITE_API_URL` 未設定 → `/api` → Vite プロキシ経由
  - 本番（Vercel）: `VITE_API_URL=https://<your-backend>.onrender.com` を設定

### バックエンドの変更点（SQLite → PostgreSQL 対応）

- `database.py`: `postgresql://` → `postgresql+asyncpg://` URL 正規化を追加
- `database.py`: `run_migrations()` は SQLite ローカル開発用として残す（PostgreSQL ではスキップ）
- `routers/digest.py`: `INSERT OR IGNORE` → `INSERT INTO ... ON CONFLICT DO NOTHING`（PostgreSQL 構文）
- `pyproject.toml`: `asyncpg` を依存関係に追加

### セットアップ手順（初回）

1. Neon でプロジェクト作成 → 接続文字列を取得（`DATABASE_URL`）
2. Render Web Service 作成（`backend/` ディレクトリ、Python 環境）
   - 環境変数を設定（`DATABASE_URL`、`GEMINI_API_KEY` 等）
   - Build Command: `pip install -r requirements.txt`（または `uv sync`）
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Vercel でプロジェクト作成（`frontend/` ディレクトリ）
   - 環境変数: `VITE_API_URL=https://<your-backend>.onrender.com`
4. Google OAuth2 の Redirect URI を本番 URL に更新
5. UptimeRobot でバックエンドの `/health` を 5 分間隔で監視設定
6. GitHub Actions の secrets に `BACKEND_URL`・`TRIGGER_API_KEY` を設定

---

## 15. 将来拡張（スコープ外）

- arXiv以外のURL（meta.ai 等）ソース対応
