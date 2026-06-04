/**
 * UTC の日時文字列（ISO 8601）を JST の表示文字列に変換する。
 * DB・API はすべて UTC で保持し、表示のみ JST に変換する。
 */
export function utcToJst(utcString: string): string {
  const date = new Date(utcString);
  return date.toLocaleString("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * HH:MM 形式の UTC 時刻を JST の HH:MM に変換する（スケジュール表示用）。
 */
export function utcHhmToJstHhm(utcHhMm: string): string {
  const [hStr, mStr] = utcHhMm.split(":");
  const h = parseInt(hStr ?? "0", 10);
  const m = parseInt(mStr ?? "0", 10);

  const now = new Date();
  now.setUTCHours(h, m, 0, 0);

  return now.toLocaleTimeString("ja-JP", {
    timeZone: "Asia/Tokyo",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * HH:MM 形式の JST 時刻を UTC の HH:MM に変換する（フォーム入力値の保存前変換）。
 */
export function jstHhmToUtcHhm(jstHhMm: string): string {
  const [hStr, mStr] = jstHhMm.split(":");
  const h = parseInt(hStr ?? "0", 10);
  const m = parseInt(mStr ?? "0", 10);

  // JST = UTC+9
  const totalMinutesUtc = (h * 60 + m - 9 * 60 + 1440) % 1440;
  const utcH = Math.floor(totalMinutesUtc / 60);
  const utcM = totalMinutesUtc % 60;

  return `${String(utcH).padStart(2, "0")}:${String(utcM).padStart(2, "0")}`;
}
