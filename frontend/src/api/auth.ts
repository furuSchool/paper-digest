import { api, BASE_URL } from "./client";

export interface AuthStatus {
  authenticated: boolean;
  token_expiry: string | null;
}

export const authApi = {
  status: (): Promise<AuthStatus> => api.get("/auth/status"),
  startOAuth: () => {
    window.location.href = `${BASE_URL}/auth/google`;
  },
  revoke: (): Promise<void> => api.delete("/auth/google"),
};
