import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { sourcesApi, type SourceCreate } from "../api/sources";
import { jstHhmToUtcHhm, utcHhmToJstHhm } from "../utils/timezone";

const ARXIV_CATEGORY_PRESETS: { id: string; desc: string }[] = [
  { id: "cs.AI",   desc: "Artificial Intelligence" },
  { id: "cs.LG",   desc: "Machine Learning" },
  { id: "cs.NE",   desc: "Neural and Evolutionary Computing" },
  { id: "cs.CV",   desc: "Computer Vision and Pattern Recognition" },
  { id: "cs.CL",   desc: "Computation and Language" },
  { id: "cs.IR",   desc: "Information Retrieval" },
  { id: "cs.GR",   desc: "Graphics" },
  { id: "cs.RO",   desc: "Robotics" },
  { id: "cs.MA",   desc: "Multiagent Systems" },
];

const ARXIV_CAT_PATTERN = /^[a-z-]+\.[A-Z]{2,}$/;

type FormInterest = {
  arxiv_categories: string[];
  keywords: string[];
};

const DEFAULT_INTEREST: FormInterest = {
  arxiv_categories: [],
  keywords: [],
};

export default function SourceForm() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEdit = id !== undefined && id !== "new";

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [scheduleFrequency, setScheduleFrequency] = useState("daily");
  const [scheduleTimeJst, setScheduleTimeJst] = useState("09:00");
  const [emailTo, setEmailTo] = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [period, setPeriod] = useState(7);
  const [googleDriveFolderId, setGoogleDriveFolderId] = useState("");
  const [interest, setInterest] = useState<FormInterest>(DEFAULT_INTEREST);
  const [keywordInput, setKeywordInput] = useState("");
  const [customCatInput, setCustomCatInput] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isEdit) return;
    sourcesApi.list().then((sources) => {
      const source = sources.find((s) => s.id === Number(id));
      if (!source) return;
      setName(source.name);
      setDescription(source.description);
      setEnabled(source.enabled);
      setScheduleFrequency(source.schedule_frequency === 1 ? "daily" : "weekly");
      setScheduleTimeJst(utcHhmToJstHhm(source.schedule_time));
      setEmailTo(source.email_to);
      setMaxResults(source.max_results);
      setPeriod(source.period);
      setGoogleDriveFolderId(source.google_drive_folder_id ?? "");
      if (source.interests.length > 0 && source.interests[0]) {
        const { id: _id, ...rest } = source.interests[0];
        setInterest({
          arxiv_categories: rest.arxiv_categories
            ? rest.arxiv_categories.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
          keywords: rest.keywords
            ? rest.keywords.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
        });
        setKeywordInput(rest.keywords);
      }
    });
  }, [id, isEdit]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    const data: SourceCreate = {
      name,
      description,
      enabled,
      schedule_frequency: scheduleFrequency === "daily" ? 1 : 7,
      schedule_time: jstHhmToUtcHhm(scheduleTimeJst),
      email_to: emailTo,
      max_results: maxResults,
      period,
      google_drive_folder_id: googleDriveFolderId || null,
      interests: [
        {
          arxiv_categories: interest.arxiv_categories.join(","),
          keywords: keywordInput
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean)
            .join(","),
        },
      ],
    };

    try {
      if (isEdit) {
        await sourcesApi.update(Number(id), data);
      } else {
        await sourcesApi.create(data);
      }
      navigate("/");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "保存に失敗しました");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleCategory = (cat: string) => {
    setInterest((prev) => ({
      ...prev,
      arxiv_categories: prev.arxiv_categories.includes(cat)
        ? prev.arxiv_categories.filter((c) => c !== cat)
        : [...prev.arxiv_categories, cat],
    }));
  };

  const addCustomCategory = () => {
    const cat = customCatInput.trim();
    if (!ARXIV_CAT_PATTERN.test(cat)) {
      alert("カテゴリは「cs.LG」のような形式で入力してください");
      return;
    }
    if (interest.arxiv_categories.includes(cat)) {
      setCustomCatInput("");
      return;
    }
    setInterest((prev) => ({
      ...prev,
      arxiv_categories: [...prev.arxiv_categories, cat],
    }));
    setCustomCatInput("");
  };

  return (
    <div style={{ maxWidth: "600px" }}>
      <h1>{isEdit ? "ソース編集" : "新規ソース"}</h1>
      <form onSubmit={handleSubmit}>
        <fieldset style={{ marginBottom: "16px", padding: "12px" }}>
          <legend>基本設定</legend>
          <div style={{ marginBottom: "8px" }}>
            <label>名前<br />
              <input value={name} onChange={(e) => setName(e.target.value)} required style={{ width: "100%" }} />
            </label>
          </div>
          <div style={{ marginBottom: "8px" }}>
            <label>説明<br />
              <input value={description} onChange={(e) => setDescription(e.target.value)} style={{ width: "100%" }} />
            </label>
          </div>
          <div style={{ marginBottom: "8px" }}>
            <label>
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              {" "}有効
            </label>
          </div>
        </fieldset>

        <fieldset style={{ marginBottom: "16px", padding: "12px" }}>
          <legend>スケジュール</legend>
          <div style={{ marginBottom: "8px" }}>
            <label>頻度<br />
              <select value={scheduleFrequency} onChange={(e) => setScheduleFrequency(e.target.value)}>
                <option value="daily">毎日</option>
                <option value="weekly">毎週</option>
              </select>
            </label>
          </div>
          <div style={{ marginBottom: "8px" }}>
            <label>実行時刻 (JST)<br />
              <input
                type="time"
                value={scheduleTimeJst}
                onChange={(e) => setScheduleTimeJst(e.target.value)}
                required
              />
            </label>
          </div>
        </fieldset>

        <fieldset style={{ marginBottom: "16px", padding: "12px" }}>
          <legend>収集設定</legend>
          <div style={{ marginBottom: "8px" }}>
            <label>最大取得件数<br />
              <input type="number" min={1} max={50} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))} />
            </label>
          </div>
          <div style={{ marginBottom: "8px" }}>
            <label>対象期間（日）<br />
              <input type="number" min={1} max={30} value={period} onChange={(e) => setPeriod(Number(e.target.value))} />
            </label>
          </div>
        </fieldset>

        <fieldset style={{ marginBottom: "16px", padding: "12px" }}>
          <legend>興味設定</legend>
          <div style={{ marginBottom: "8px" }}>
            <label>arXivカテゴリ</label>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }}>
              {ARXIV_CATEGORY_PRESETS.map(({ id: cat, desc }) => (
                <label key={cat} style={{ fontSize: "14px" }}>
                  <input
                    type="checkbox"
                    checked={interest.arxiv_categories.includes(cat)}
                    onChange={() => toggleCategory(cat)}
                  />
                  {" "}{cat}<span style={{ color: "#888", fontSize: "12px" }}> ({desc})</span>
                </label>
              ))}
            </div>
            <div style={{ marginTop: "10px", fontSize: "12px", color: "#888", marginBottom: "4px" }}>カスタム追加</div>
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              <input
                value={customCatInput}
                onChange={(e) => setCustomCatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomCategory())}
                placeholder="例: cs.AI"
                style={{ width: "140px" }}
              />
              <button type="button" onClick={addCustomCategory}>追加</button>
            </div>
            {interest.arxiv_categories.filter(
              (cat) => !ARXIV_CATEGORY_PRESETS.map((c) => c.id).includes(cat)
            ).length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                {interest.arxiv_categories
                  .filter((cat) => !ARXIV_CATEGORY_PRESETS.map((c) => c.id).includes(cat))
                  .map((cat) => (
                    <span
                      key={cat}
                      style={{ background: "#eee", borderRadius: "4px", padding: "2px 8px", fontSize: "13px" }}
                    >
                      {cat}
                      <button
                        type="button"
                        onClick={() => toggleCategory(cat)}
                        style={{ marginLeft: "4px", background: "none", border: "none", cursor: "pointer", color: "#888" }}
                      >×</button>
                    </span>
                  ))}
              </div>
            )}
          </div>
          <div style={{ marginBottom: "8px" }}>
            <label>キーワード（カンマ区切り）<br />
              <input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                placeholder="例: diffusion,transformer"
                style={{ width: "100%" }}
              />
            </label>
          </div>
        </fieldset>

        <fieldset style={{ marginBottom: "16px", padding: "12px" }}>
          <legend>通知設定</legend>
          <div style={{ marginBottom: "8px" }}>
            <label>通知先メールアドレス<br />
              <input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} required style={{ width: "100%" }} />
            </label>
          </div>
          <div style={{ marginBottom: "8px" }}>
            <label>Google Drive フォルダID（任意）<br />
              <input value={googleDriveFolderId} onChange={(e) => setGoogleDriveFolderId(e.target.value)} style={{ width: "100%" }} />
            </label>
          </div>
        </fieldset>

        <div>
          <button type="submit" disabled={submitting}>
            {submitting ? "保存中..." : "保存"}
          </button>
          <button type="button" onClick={() => navigate("/")} style={{ marginLeft: "8px" }}>
            キャンセル
          </button>
        </div>
      </form>
    </div>
  );
}
