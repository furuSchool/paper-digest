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
  schedule_time: string;
  email_to: string;
  max_results: number;
  period: number;
  google_drive_folder_id: string | null;
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
