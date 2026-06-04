import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { sourcesApi, type Source } from "../api/sources";
import { utcHhmToJstHhm } from "../utils/timezone";

export default function Dashboard() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    sourcesApi
      .list()
      .then(setSources)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "取得に失敗しました")
      )
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (source: Source) => {
    try {
      const updated = await sourcesApi.update(source.id, {
        enabled: !source.enabled,
      });
      setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "更新に失敗しました");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("このソースを削除しますか？")) return;
    try {
      await sourcesApi.remove(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "削除に失敗しました");
    }
  };

  if (loading) return <p>読み込み中...</p>;
  if (error) return <p style={{ color: "red" }}>{error}</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>ダッシュボード</h1>
        <Link to="/sources/new">
          <button>+ 新規ソース</button>
        </Link>
      </div>

      {sources.length === 0 ? (
        <p>ソースが登録されていません。新規ソースを追加してください。</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "8px", borderBottom: "1px solid #ccc" }}>名前</th>
              <th style={{ textAlign: "left", padding: "8px", borderBottom: "1px solid #ccc" }}>スケジュール (JST)</th>
              <th style={{ textAlign: "left", padding: "8px", borderBottom: "1px solid #ccc" }}>有効</th>
              <th style={{ textAlign: "left", padding: "8px", borderBottom: "1px solid #ccc" }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td style={{ padding: "8px", borderBottom: "1px solid #eee" }}>
                  <strong>{s.name}</strong>
                  <br />
                  <small style={{ color: "#666" }}>{s.description}</small>
                </td>
                <td style={{ padding: "8px", borderBottom: "1px solid #eee" }}>
                  {s.schedule_frequency} {utcHhmToJstHhm(s.schedule_time)}
                </td>
                <td style={{ padding: "8px", borderBottom: "1px solid #eee" }}>
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={() => handleToggle(s)}
                  />
                </td>
                <td style={{ padding: "8px", borderBottom: "1px solid #eee" }}>
                  <Link to={`/sources/${s.id}/edit`}>
                    <button style={{ marginRight: "8px" }}>編集</button>
                  </Link>
                  <Link to={`/sources/${s.id}/preview`}>
                    <button style={{ marginRight: "8px" }}>プレビュー</button>
                  </Link>
                  <button onClick={() => handleDelete(s.id)} style={{ color: "red" }}>
                    削除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
