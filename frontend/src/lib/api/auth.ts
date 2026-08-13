import { request } from "./client";
import { User, AccessContext } from "@/types";

export const authApi = {
  async register(email: string, password: string): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  async login(email: string, password: string): Promise<User> {
    return request<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  async logout(): Promise<void> {
    await request<void>("/auth/logout", {
      method: "POST",
    });
  },

  async getMeContext(): Promise<AccessContext> {
    return request<AccessContext>("/agents/me/context", {
      method: "GET",
    });
  },
};
