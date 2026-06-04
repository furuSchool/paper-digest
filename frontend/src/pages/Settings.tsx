import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { authApi, type AuthStatus } from "../api/auth";
import { utcToJst } from "../utils/timezone";

export default function Settings() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [revoking, setRevoking] = useState(false);

  const authSuccess = searchParams.get("auth") === "success";

  useEffect(() => {
    authApi
      .status()
      .then(setStatus)
      .finally(() => setLoading(false));
  }, []);

  const handleRevoke = async () => {
    if (!confirm("Google認証を解除しますか？")) return;
    setRevoking(true);
    try {
      await authApi.revoke();
      setStatus({ authenticated: false, token_expiry: null });
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "解除に失敗しました");
    } finally {
      setRevoking(false);
    }
  };

  return (
    <div>
      <h1>設定</h1>

      {authSuccess && (
        <p style={{ color: "green", background: "#e8f5e9", padding: "8px", borderRadius: "4px" }}>
          Google認証が完了しました。
        </p>
      )}

      <section style={{ marginBottom: "24px" }}>
        <h2>Google認証</h2>
        {loading ? (
          <p>読み込み中...</p>
        ) : status?.authenticated ? (
          <div>
            <p style={{ color: "green" }}>認証済み</p>
            {status.token_expiry && (
              <p style={{ fontSize: "14px", color: "#666" }}>
                有効期限: {utcToJst(status.token_expiry)}
              </p>
            )}
            <button onClick={handleRevoke} disabled={revoking} style={{ color: "red" }}>
              {revoking ? "解除中..." : "認証を解除する"}
            </button>
          </div>
        ) : (
          <div>
            <p style={{ color: "orange" }}>未認証</p>
            <p style={{ fontSize: "14px", color: "#666" }}>
              Google DocsへのDoc作成・GmailでのメールにはGoogle認証が必要です。
            </p>
            <button onClick={authApi.startOAuth}>
              Googleアカウントで認証する
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
