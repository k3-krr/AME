import { request } from "./client";
import { Conversation, Message } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface CreateConversationPayload {
  title?: string | null;
  system_prompt?: string | null;
}

export interface SendMessagePayload {
  content: string;
}

export const chatApi = {
  /**
   * Retrieves a list of active conversations.
   */
  async listConversations(page: number = 1, limit: number = 20): Promise<Conversation[]> {
    return request<Conversation[]>(`/conversations?page=${page}&limit=${limit}`, {
      method: "GET",
    });
  },

  /**
   * Creates a new conversation canvas.
   */
  async createConversation(payload: CreateConversationPayload): Promise<Conversation> {
    return request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Deletes a conversation and its messages.
   */
  async deleteConversation(conversationId: string): Promise<void> {
    return request<void>(`/conversations/${conversationId}`, {
      method: "DELETE",
    });
  },

  /**
   * Fetches messages history for a conversation using cursor-based pagination.
   */
  async listMessages(
    conversationId: string, 
    limit: number = 50, 
    beforeId?: string
  ): Promise<Message[]> {
    let query = `/conversations/${conversationId}/messages?limit=${limit}`;
    if (beforeId) {
      query += `&before_id=${beforeId}`;
    }
    return request<Message[]>(query, {
      method: "GET",
    });
  },

  /**
   * Initiates message submit and returns raw Response with ReadableStream.
   * Preserves session credentials and authentication cookies.
   */
  async postMessageStream(conversationId: string, content: string): Promise<Response> {
    const url = `${BASE_URL}/conversations/${conversationId}/messages`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
      credentials: "include", // Essential for HttpOnly session cookie parsing
    });
    return response;
  },
};
