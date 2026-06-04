import { api } from "./client";

export interface PaperSummary {
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  url: string;
  summary_ja: string;
  matched_by_keyword: boolean;
}

export interface DigestResult {
  source_id: number;
  papers: PaperSummary[];
  doc_url: string | null;
}

export const digestApi = {
  preview: (sourceId: number, useMock = false): Promise<DigestResult> =>
    api.post(`/digest/preview/${sourceId}${useMock ? "?use_mock=true" : ""}`),
  run: (sourceId: number, useMock = false): Promise<DigestResult> =>
    api.post(`/digest/run/${sourceId}${useMock ? "?use_mock=true" : ""}`),
};
