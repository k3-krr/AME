import { create } from 'zustand';

interface ChatState {
  activeConversationId: string | null;
  isStreaming: boolean;
  setActiveConversationId: (id: string | null) => void;
  setStreaming: (streaming: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  activeConversationId: null,
  isStreaming: false,
  setActiveConversationId: (id) => set({ activeConversationId: id }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
}));
