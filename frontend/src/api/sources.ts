import { api } from "./client";

export interface SourceInterest {
  id?: number;
  arxiv_categories: string;
  keywords: string;
}

export interface Source {
  id: number;
  name: string;
  description: string;
  enabled: boolean;
  schedule_frequency: number;
  last_triggered_at: string | null;
  email_to: string;
  max_results: number;
  period: number;
  google_drive_folder_id: string | null;
  dedup_enabled: boolean;
  citation_filter_enabled: boolean;
  citation_top_multiplier: number;
  llm_prompt: string | null;
  created_at: string;
  interests: SourceInterest[];
}

export type SourceCreate = Omit<Source, "id" | "created_at"> & {
  interests: Omit<SourceInterest, "id">[];
};

export type SourceUpdate = Partial<SourceCreate>;

export const sourcesApi = {
  list: (): Promise<Source[]> => api.get("/sources"),
  create: (data: SourceCreate): Promise<Source> => api.post("/sources", data),
  update: (id: number, data: SourceUpdate): Promise<Source> =>
    api.put(`/sources/${id}`, data),
  remove: (id: number): Promise<void> => api.delete(`/sources/${id}`),
};
