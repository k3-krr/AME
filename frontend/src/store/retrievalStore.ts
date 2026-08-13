import { create } from "zustand";
import { 
  GroundedContextPackage, 
  GroundedPromptPackage, 
  QueryAnalysisResult, 
  QueryRewriteResult 
} from "@/types";
import { retrievalApi } from "@/lib/api/retrieval";
import { ApiError } from "@/lib/api/client";

interface RetrievalState {
  query: string;
  contextPackage: GroundedContextPackage | null;
  promptPackage: GroundedPromptPackage | null;
  analysisResult: QueryAnalysisResult | null;
  rewriteResult: QueryRewriteResult | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setQuery: (query: string) => void;
  executeRetrieve: (conversationId?: string | null, options?: Record<string, unknown> | null) => Promise<void>;
  executeGround: (conversationId?: string | null, options?: Record<string, unknown> | null) => Promise<void>;
  executeAnalyze: () => Promise<void>;
  executeRewrite: () => Promise<void>;
  clearResults: () => void;
  resetRetrievalStore: () => void;
}

export const useRetrievalStore = create<RetrievalState>((set, get) => ({
  query: "",
  contextPackage: null,
  promptPackage: null,
  analysisResult: null,
  rewriteResult: null,
  isLoading: false,
  error: null,

  resetRetrievalStore: () => set({
    query: "",
    contextPackage: null,
    promptPackage: null,
    analysisResult: null,
    rewriteResult: null,
    isLoading: false,
    error: null,
  }),

  setQuery: (query: string) => set({ query }),

  clearResults: () => set({
    contextPackage: null,
    promptPackage: null,
    analysisResult: null,
    rewriteResult: null,
    error: null,
  }),

  executeRetrieve: async (conversationId = null, options = null) => {
    const { query } = get();
    if (!query.trim()) return;

    set({ isLoading: true, error: null });
    try {
      const res = await retrievalApi.retrieveContext({
        query: query.trim(),
        conversation_id: conversationId || undefined,
        options: options || undefined,
      });
      set({ contextPackage: res });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Context retrieval process failed." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  executeGround: async (conversationId = null, options = null) => {
    const { query } = get();
    if (!query.trim()) return;

    set({ isLoading: true, error: null });
    try {
      const res = await retrievalApi.groundRetrieval({
        query: query.trim(),
        conversation_id: conversationId || undefined,
        options: options || undefined,
      });
      set({ promptPackage: res });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Context grounding process failed." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  executeAnalyze: async () => {
    const { query } = get();
    if (!query.trim()) return;

    set({ isLoading: true, error: null });
    try {
      const res = await retrievalApi.analyzeQuery({
        query: query.trim(),
      });
      set({ analysisResult: res });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Query analysis process failed." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  executeRewrite: async () => {
    const { query } = get();
    if (!query.trim()) return;

    set({ isLoading: true, error: null });
    try {
      const res = await retrievalApi.rewriteQuery({
        query: query.trim(),
      });
      set({ rewriteResult: res });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Query rewriting process failed." });
      }
    } finally {
      set({ isLoading: false });
    }
  },
}));
