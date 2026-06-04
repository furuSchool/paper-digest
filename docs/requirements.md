## 1. システム概要

個人用リサーチダイジェストツール。arXivの最新論文を自動収集・キーワードフィルタリングし、LLMで日本語要約を生成。Google Docsにまとめ、GmailでDoc URLを通知する。React + FastAPIで構築し、フロントから全設定を管理できる。

### 目的

特定の自分にフィットした分野の最新情報を、概要だけすばやくチェックし、詳しく見たいものは元リンクへ飛べるようにする。

---

## 2. アーキテクチャ

```
[GitHub Actions]（定期実行 / cron）
  └── バックエンドの /digest/trigger をHTTPで叩く

[React Frontend]
  ↕ REST API
[FastAPI Backend]
  ├── arXiv API（論文取得）
  ├── Gemini API（要約生成のみ）
  ├── Google Docs API（ドキュメント作成・書き込み）
  └── Gmail API（メール送信）

[SQLite]（設定データのみ保存）
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
| schedule_frequency | INTEGER | `1` なら毎日、`7` なら週1回 |
| schedule_time | TEXT | 配信時刻（UTC で保存。例: `23:00`） |
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
| 配信頻度 | セレクト（daily / weekly） |  |
| 配信時刻 | 時刻ピッカー | JSTで入力 → UTC変換してAPI送信 |
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
| POST | `/digest/trigger` | GitHub Actionsから呼ばれる。現在時刻と一致するソースを全実行 |
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
| DBの保存値（schedule_time 等） | UTC |
| バックエンド処理・GitHub Actions | UTC |
| フロントの表示・入力 | JST（UTC+9） |
| フロント→API通信 | JSTで入力 → 送信前にUTC変換 |

---

## 9. 定期実行（GitHub Actions）

```yaml
# .github/workflows/digest.yml

name: Run Digest
on:
  schedule:
    - cron: '0 * * * *'   # 毎時00分にUTCで実行
  workflow_dispatch:       # 手動実行も可

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger digest
        run: |
          curl -X POST ${{ secrets.BACKEND_URL }}/digest/trigger \
            -H "X-API-Key: ${{ secrets.TRIGGER_API_KEY }}"
```

- バックエンドの `/digest/trigger` は、現在時刻（UTC）と一致する `schedule_time` を持つ有効なソースを全て実行する
- `TRIGGER_API_KEY` による簡易認証でエンドポイントを保護する

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
| DB | SQLite + SQLAlchemy |
| LLM | Gemini API（`gemini-3.1-flash-lite`）※要約のみ |
| 外部API | arXiv API, Google Docs API, Gmail API, Google Drive API |
| 認証 | Google OAuth2（Docs + Gmail + Drive 一本化） |
| 定期実行 | GitHub Actions（cron） |
| デプロイ | Render 無料枠 |

---

## 12. 環境変数（`.env`）

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

## 14. 将来拡張（スコープ外）

- arXiv以外のURL（meta.ai 等）ソース対応
