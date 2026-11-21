import { create } from "zustand";
import { Conversation, Message } from "@/types";
import { chatApi } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/client";

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  isStreaming: boolean;
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;
  error: string | null;

  // Actions
  fetchConversations: (page?: number, limit?: number) => Promise<void>;
  createConversation: (title?: string | null, systemPrompt?: string | null) => Promise<string | null>;
  deleteConversation: (conversationId: string) => Promise<void>;
  selectConversation: (conversationId: string) => Promise<void>;
  sendMessageStream: (content: string) => Promise<void>;
  clearError: () => void;
  resetChatStore: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  isLoadingConversations: false,
  isLoadingMessages: false,
  error: null,

  clearError: () => set({ error: null }),

  resetChatStore: () => set({
    conversations: [],
    activeConversationId: null,
    messages: [],
    isStreaming: false,
    isLoadingConversations: false,
    isLoadingMessages: false,
    error: null,
  }),

  fetchConversations: async (page = 1, limit = 20) => {
    set({ isLoadingConversations: true, error: null });
    try {
      const data = await chatApi.listConversations(page, limit);
      set({ conversations: data });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to fetch conversations." });
      }
    } finally {
      set({ isLoadingConversations: false });
    }
  },

  createConversation: async (title = null, systemPrompt = null) => {
    set({ error: null });
    try {
      const newConv = await chatApi.createConversation({
        title: title || "New Conversation",
        system_prompt: systemPrompt,
      });
      set((state) => ({
        conversations: [newConv, ...state.conversations],
        activeConversationId: newConv.id,
        messages: [],
      }));
      return newConv.id;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to create conversation." });
      }
      return null;
    }
  },

  selectConversation: async (conversationId: string) => {
    set({ activeConversationId: conversationId, isLoadingMessages: true, error: null, messages: [] });
    try {
      const messagesData = await chatApi.listMessages(conversationId);
      // Backend list returns oldest first or newest first?
      // Typically, list_messages returns in ascending order or needs reverse. Let's inspect the order.
      // If messages are returned with oldest first, we keep it. If newest first, we reverse it so layout streams down.
      // Let's sort them by created_at or use the order returned. Let's sort ascending by created_at to render sequentially.
      const sortedMessages = [...messagesData].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
      set({ messages: sortedMessages });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to load messages." });
      }
    } finally {
      set({ isLoadingMessages: false });
    }
  },

  deleteConversation: async (conversationId: string) => {
    set({ error: null });
    try {
      await chatApi.deleteConversation(conversationId);
      const isActive = get().activeConversationId === conversationId;
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== conversationId),
        activeConversationId: isActive ? null : state.activeConversationId,
        messages: isActive ? [] : state.messages,
      }));
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to delete conversation." });
      }
    }
  },

  sendMessageStream: async (content: string) => {
    const activeId = get().activeConversationId;
    if (!activeId) {
      set({ error: "No active conversation selected." });
      return;
    }
    if (get().isStreaming) return;

    set({ isStreaming: true, error: null });

    // Generate temporary IDs for instantaneous feedback
    const tempUserMsgId = `temp-user-${Date.now()}`;
    const tempAssistantMsgId = `temp-assistant-${Date.now()}`;

    const tempUserMsg: Message = {
      id: tempUserMsgId,
      conversation_id: activeId,
      sender_role: "user",
      content,
      memory_status: "pending",
      created_at: new Date().toISOString(),
    };

    const tempAssistantMsg: Message = {
      id: tempAssistantMsgId,
      conversation_id: activeId,
      sender_role: "assistant",
      content: "",
      memory_status: "pending",
      created_at: new Date().toISOString(),
    };

    // Append user & assistant placeholder to message log
    set((state) => ({
      messages: [...state.messages, tempUserMsg, tempAssistantMsg],
    }));

    let currentAssistantMsgId = tempAssistantMsgId;

    try {
      const response = await chatApi.postMessageStream(activeId, content);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} failed to initiate stream.`);
      }

      const body = response.body;
      if (!body) {
        throw new Error("Empty streaming response body.");
      }

      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) break;

        // Decode chunks and replace Windows \r\n with \n for unified sse split processing
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, "\n");

        let boundaryIndex;
        while ((boundaryIndex = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, boundaryIndex).trim();
          buffer = buffer.slice(boundaryIndex + 2);

          if (block) {
            // Parse event blocks
            const lines = block.split("\n");
            let sseEvent = "";
            let sseData = "";

            for (const line of lines) {
              if (line.startsWith("event: ")) {
                sseEvent = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                sseData = line.slice(6).trim();
              }
            }

            if (sseEvent === "message_id") {
              const realId = sseData;
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === currentAssistantMsgId ? { ...m, id: realId } : m
                ),
              }));
              currentAssistantMsgId = realId;
            } else if (sseEvent === "delta") {
              // Append text chunk token to active assistant message
              const token = sseData;
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === currentAssistantMsgId ? { ...m, content: m.content + token } : m
                ),
              }));
            } else if (sseEvent === "error") {
              throw new Error(sseData || "Stream generation error from server.");
            } else if (sseEvent === "done") {
              // Done event, break process
              break;
            }
          }
        }
      }

      // Sync with DB to load metadata like updated dates & memory_status flags
      const refreshedMessages = await chatApi.listMessages(activeId);
      const sortedRefreshed = [...refreshedMessages].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
      set({ messages: sortedRefreshed });

      // Start non-blocking status polling if there are pending assistant messages
      const hasPending = sortedRefreshed.some(
        (m) => m.sender_role === "assistant" && m.memory_status === "pending"
      );

      if (hasPending) {
        let attempts = 0;
        const maxAttempts = 8; // ~16 seconds total limit
        const pollInterval = 2000;

        const pollStatus = async () => {
          if (attempts >= maxAttempts) return;
          if (get().activeConversationId !== activeId) return;

          await new Promise((resolve) => setTimeout(resolve, pollInterval));

          if (get().activeConversationId !== activeId) return;

          try {
            const latestMessages = await chatApi.listMessages(activeId);
            const sorted = [...latestMessages].sort(
              (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
            );

            // Sync frontend messages with latest status
            set({ messages: sorted });

            const stillPending = sorted.some(
              (m) => m.sender_role === "assistant" && m.memory_status === "pending"
            );

            if (stillPending) {
              attempts++;
              pollStatus();
            }
          } catch (pollErr) {
            console.error("Failed to poll message memory status:", pollErr);
          }
        };

        // Invoke asynchronously without blocking the main send flow completion
        pollStatus();
      }


    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to process stream response.";
      set({ error: errorMsg });
      // Remove the failed placeholder if it remained empty
      set((state) => ({
        messages: state.messages.filter((m) => m.id !== tempAssistantMsgId && m.id !== currentAssistantMsgId),
      }));
    } finally {
      set({ isStreaming: false });
    }
  },
}));
