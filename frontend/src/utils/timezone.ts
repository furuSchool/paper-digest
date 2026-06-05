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
