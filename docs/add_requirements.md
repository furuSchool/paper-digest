# 追加機能 要件定義

## 概要

以下3機能を追加する。いずれもソースごとに有効/無効を切り替え可能。

---

## 1. 重複配信防止（Deduplication）

### 概要

過去に配信済みの論文を、次回の配信対象から除外する。

### データモデル変更

#### `sources` テーブルへの追加カラム

| カラム | 型 | デフォルト | 説明 |
| --- | --- | --- | --- |
| `dedup_enabled` | BOOLEAN | TRUE | 重複配信防止の有効/無効 |

#### 新規テーブル `delivered_papers`

| カラム | 型 | 説明 |
| --- | --- | --- |
| id | INTEGER | PK |
| source_id | INTEGER | FK → sources.id |
| arxiv_id | TEXT | 配信済みのarXiv論文ID |
| delivered_at | DATETIME | 配信日時（UTC） |

- `(source_id, arxiv_id)` にユニーク制約を付ける

### 処理フロー変更

arXiv から論文を取得したあと、`max_results` 件にサンプリングする**前**に除外処理を挟む：

```
① arXiv fetch（MAX_PAPERS_PER_QUERY件取得）
② dedup_enabled=True の場合：
     delivered_papers テーブルから当該 source_id の arxiv_id 一覧を取得
     → 取得論文から除外
③ max_results 件にランダムサンプリング
④ LLM 要約
⑤ Docs 書き込み・メール送信（send=True の場合）
⑥ dedup_enabled=True かつ send=True の場合：
     配信した論文の arxiv_id を delivered_papers に INSERT
```

### 注意事項

- プレビュー（`send=False`）時は `delivered_papers` に書き込まない
- モックモード時は除外も書き込みもしない
- 除外後に候補が `max_results` 未満でも、そのまま全件配信する（エラーにしない）

### API変更

- `GET /sources`・`POST /sources`・`PUT /sources/:id` に `dedup_enabled` を追加

### フロントエンド変更

- SourceForm の「基本設定」に「重複配信防止」チェックボックスを追加（デフォルトON）

---

## 2. 引用数フィルタリング（Citation Filter）

### 概要

Semantic Scholar API をキーワードで検索し、引用数上位の論文を取得する。その後、arxiv ID を使って arXiv から詳細データを取得する。arXiv fetch は最後に行う。

### データモデル変更

#### `sources` テーブルへの追加カラム

| カラム | 型 | デフォルト | 説明 |
| --- | --- | --- | --- |
| `citation_filter_enabled` | BOOLEAN | FALSE | 引用数フィルタリングの有効/無効 |
| `citation_top_multiplier` | INTEGER | 5 | 引用数上位候補を `max_results × citation_top_multiplier` 件に絞る倍率 |

### 新規サービス `semantic_scholar_service.py`

```
backend/services/semantic_scholar_service.py
```

#### 主要関数

```python
async def search_by_citation(
    keywords: list[str],
    limit: int,
) -> list[tuple[str, int]]:
    """
    キーワードで Semantic Scholar を検索し、
    引用数降順で上位 limit 件の (arxiv_id, citation_count) リストを返す。
    arXiv に存在しない論文（externalIds.ArXiv が null）は除外する。
    """
```

#### Semantic Scholar API 仕様

- エンドポイント: `GET https://api.semanticscholar.org/graph/v1/paper/search/bulk`
- クエリパラメータ:
  - `query=<keywords を空白結合>`
  - `fields=citationCount,externalIds`
  - `sort=citationCount:desc`
- レスポンス例:
  ```json
  {
    "data": [
      {"paperId": "...", "citationCount": 120, "externalIds": {"ArXiv": "2406.00001"}},
      {"paperId": "...", "citationCount": 80,  "externalIds": {"ArXiv": null}},
      ...
    ],
    "token": "<next_page_token>"
  }
  ```
- ページネーション: `token` を使って続きを取得。`limit * 3` 件程度を上限に取得し、arXiv 論文のみ残して上位 `limit` 件に絞る
- レートリミット:
  - APIキーなし: 1リクエスト/秒
  - APIキーあり: 10リクエスト/秒
- 認証: `x-api-key` ヘッダー（任意）

#### 環境変数（任意）

```
SEMANTIC_SCHOLAR_API_KEY=
```

`.env.example` にも追記する。

### 処理フロー

#### `citation_filter_enabled=False`（既存の動作）

```
① arXiv 検索（カテゴリ＋キーワード＋日付範囲、MAX_PAPERS_PER_QUERY件）
② dedup 除外
③ max_results 件にランダムサンプリング
④ LLM 要約
⑤ Docs・メール送信
```

#### `citation_filter_enabled=True`（新フロー）

```
① Semantic Scholar をキーワードで検索（引用数降順）
     → arXiv 論文のみ残す
     → 上位 max_results × citation_top_multiplier 件の (arxiv_id, citation_count) を取得
② dedup_enabled=True の場合：配信済み arxiv_id を除外
③ max_results 件にランダムサンプリング（citation_count も保持）
④ arXiv からその arxiv_id リストで論文詳細を取得
     （arxiv.Search(id_list=[...]) を使用）
⑤ LLM 要約
⑥ Docs・メール送信
```

- `matched_by_keyword` フラグ: キーワードが設定されていれば True
- カテゴリフィルタは `citation_filter_enabled=True` 時は適用しない（Semantic Scholar がカテゴリ絞り込みに非対応のため）

### 注意事項

- Semantic Scholar の検索は年単位フィルタのみ対応。`period_days` による日単位の精密絞り込みは行わない（引用数ランキング重視）
- 候補が `max_results` 未満の場合はそのまま全件を使う
- Semantic Scholar API のタイムアウトは 30 秒。タイムアウト・エラー時はフォールバックとして `citation_filter_enabled=False` の通常フローを実行する（エラーにしない）
- キーワードが未設定の場合は `citation_filter_enabled` を無視して通常フローを実行する
- モックモード時はスキップ

### 引用数の表示

Google Docs・Gmail 本文の各論文カードにて、著者の後に引用数を表示する：

```
[1] Title (English)
Authors: Alice Smith, Bob Johnson
引用数: 42
[キーワード一致 / ランダム選択]
Abstract: ...
日本語要約: ...
```

- `citation_filter_enabled=False` の通常フロー時は引用数を取得しないため、引用数行は表示しない

### `PaperSummary` スキーマ変更

```python
class PaperSummary(BaseModel):
    ...
    citation_count: int | None = None  # 引用数フィルタ使用時のみ設定
```

### API変更

- `GET /sources`・`POST /sources`・`PUT /sources/:id` に `citation_filter_enabled`・`citation_top_multiplier` を追加

### フロントエンド変更

- SourceForm の「収集設定」に以下を追加：
  - 「引用数フィルタリング」チェックボックス（デフォルトOFF）
  - `citation_filter_enabled=True` のとき：
    - 「候補倍率」数値入力（デフォルト5、最小1）を表示
    - arXiv カテゴリの fieldset を非表示にする（Semantic Scholar はカテゴリ非対応のため）
  - `citation_filter_enabled=False` のとき：arXiv カテゴリの fieldset を通常通り表示

---

## 3. LLM要約プロンプトのカスタマイズ

### 概要

ソースごとに、LLMへの要約指示を追加できるようにする。設定がない場合はデフォルトプロンプトのみ使用する。

### データモデル変更

#### `sources` テーブルへの追加カラム

| カラム | 型 | デフォルト | 説明 |
| --- | --- | --- | --- |
| `llm_prompt` | TEXT | NULL | 要約時の追加指示（任意） |

### `llm_service.summarize_papers` の変更

```python
async def summarize_papers(
    papers: list[ArxivPaper],
    extra_prompt: str | None = None,
) -> dict[str, str]:
```

- `extra_prompt` が設定されている場合、基本プロンプトの末尾に追記する：

```
## 追加指示
{extra_prompt}
```

### digest.py での変更

`summarize_papers` 呼び出し時に `source.llm_prompt` を渡す。

### API変更

- `GET /sources`・`POST /sources`・`PUT /sources/:id` に `llm_prompt` を追加

### フロントエンド変更

- SourceForm の「収集設定」に「LLM要約の追加指示（任意）」テキストエリアを追加
- プレースホルダー例: `ロボティクスの実応用に関する視点を重視して要約してください`

---

## 変更ファイル一覧（予定）

### バックエンド

| ファイル | 変更内容 |
| --- | --- |
| `models.py` | `Source` に5カラム追加。`DeliveredPaper` モデル新規追加 |
| `schemas.py` | `SourceBase` に5フィールド追加。`PaperSummary` に `citation_count` 追加 |
| `database.py` | マイグレーション対応（ALTER TABLE または再作成） |
| `routers/digest.py` | 処理パイプラインに dedup・citation filter 挿入、`summarize_papers` に `extra_prompt` 渡す |
| `services/arxiv_service.py` | `fetch_papers_by_ids(id_list)` 関数を追加 |
| `services/llm_service.py` | `summarize_papers` に `extra_prompt` 引数追加 |
| `services/semantic_scholar_service.py` | **新規** |
| `services/docs_service.py` | 引用数表示を著者後に追加 |
| `services/gmail_service.py` | 引用数表示を著者後に追加 |
| `tests/test_arxiv_service.py` | `fetch_papers_by_ids` のテスト追加 |
| `tests/test_llm_service.py` | `extra_prompt` 引数のテスト追加 |
| `tests/test_semantic_scholar_service.py` | **新規** |

### フロントエンド

| ファイル | 変更内容 |
| --- | --- |
| `src/api/sources.ts` | `SourceCreate`・`SourceRead` 型に5フィールド追加 |
| `src/pages/SourceForm.tsx` | 新フィールドのUI追加。citation_filter_enabled=True 時にカテゴリ fieldset 非表示 |

### その他

| ファイル | 変更内容 |
| --- | --- |
| `.env.example` | `SEMANTIC_SCHOLAR_API_KEY=` 追記 |

---

## 未決事項・スコープ外

- `delivered_papers` の保持期間（削除ポリシー）: 初期実装では全件保持し、将来対応
- Semantic Scholar API キー取得フロー: 環境変数に手動設定する方式のみ。UIからの設定は行わない
