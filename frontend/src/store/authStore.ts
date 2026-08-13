import { create } from "zustand";
import { AccessContext } from "@/types";

interface AuthState {
  userContext: AccessContext | null;
  email: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setContext: (context: AccessContext | null, email?: string | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  userContext: null,
  email: null,
  isAuthenticated: false,
  isLoading: true, // Start with loading active until session check completes
  setContext: (context, email = null) => {
    set({
      userContext: context,
      email: email || (context?.user_id ? `user_${context.user_id.slice(0, 6)}@ame.ai` : null),
      isAuthenticated: !!context,
      isLoading: false,
    });
  },
  setLoading: (loading) => set({ isLoading: loading }),
  logout: () => {
    set({
      userContext: null,
      email: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },
}));
