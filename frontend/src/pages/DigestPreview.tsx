import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { digestApi, type DigestResult } from "../api/digest";

export default function DigestPreview() {
  const { id } = useParams<{ id: string }>();
  const sourceId = Number(id);

  const [result, setResult] = useState<DigestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useMock, setUseMock] = useState(false);

  const handlePreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await digestApi.preview(sourceId, useMock);
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "プレビュー取得に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  const handleRun = async () => {
    const confirmMsg = useMock
      ? "モックデータでGoogle DocsとGmailに送信しますか？（Gemini APIは呼びません）"
      : "ダイジェストを実行してGoogle DocsとGmailに送信しますか？";
    if (!confirm(confirmMsg)) return;
    setRunning(true);
    setError(null);
    try {
      const data = await digestApi.run(sourceId, useMock);
      setResult(data);
      alert("実行完了！" + (data.doc_url ? `\nDoc URL: ${data.doc_url}` : ""));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "実行に失敗しました");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px" }}>
        <h1 style={{ margin: 0 }}>ダイジェストプレビュー</h1>
      </div>

      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", alignItems: "center" }}>
        <button onClick={handlePreview} disabled={loading}>
          {loading ? "取得中..." : "プレビュー取得"}
        </button>
        <button onClick={handleRun} disabled={running || loading}>
          {running ? "実行中..." : "実行（Docs + Gmail送信）"}
        </button>
        <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "14px", color: "#666", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={useMock}
            onChange={(e) => setUseMock(e.target.checked)}
          />
          モックデータを使用（Gemini APIスキップ）
        </label>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {result && (
        <div>
          {result.doc_url && (
            <p>
              <strong>Google Docs:</strong>{" "}
              <a href={result.doc_url} target="_blank" rel="noreferrer">
                {result.doc_url}
              </a>
            </p>
          )}
          <p>取得論文数: {result.papers.length}</p>
          {result.papers.map((paper) => (
            <div
              key={paper.arxiv_id}
              style={{
                border: "1px solid #ddd",
                borderRadius: "4px",
                padding: "12px",
                marginBottom: "12px",
              }}
            >
              <h3 style={{ margin: "0 0 4px" }}>
                <a href={paper.url} target="_blank" rel="noreferrer">
                  {paper.title}
                </a>
              </h3>
              <p style={{ margin: "0 0 4px", color: "#666", fontSize: "14px" }}>
                {paper.authors.join(", ")} | {paper.matched_by_keyword ? "キーワード" : "ランダム選択"}
              </p>
              <p style={{ margin: "0 0 8px", fontSize: "14px" }}>{paper.abstract}</p>
              {paper.summary_ja && (
                <p style={{ margin: 0, fontSize: "14px", background: "#f5f5f5", padding: "8px", borderRadius: "4px" }}>
                  <strong>日本語要約:</strong> {paper.summary_ja}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
