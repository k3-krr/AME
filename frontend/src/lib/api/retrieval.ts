import { request } from "./client";
import { 
  RetrievalRequest, 
  GroundedContextPackage, 
  GroundedPromptPackage, 
  QueryAnalysisResult, 
  QueryRewriteResult 
} from "@/types";

export const retrievalApi = {
  async retrieveContext(payload: RetrievalRequest): Promise<GroundedContextPackage> {
    return request<GroundedContextPackage>("/retrieval/retrieve", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async groundRetrieval(payload: RetrievalRequest): Promise<GroundedPromptPackage> {
    return request<GroundedPromptPackage>("/retrieval/ground", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async analyzeQuery(payload: RetrievalRequest): Promise<QueryAnalysisResult> {
    return request<QueryAnalysisResult>("/retrieval/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async rewriteQuery(payload: RetrievalRequest): Promise<QueryRewriteResult> {
    return request<QueryRewriteResult>("/retrieval/rewrite", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
