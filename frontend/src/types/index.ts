// Adaptive Memory Engine (AME) - Frontend Common Type Definitions

export interface User {
  id: string;
  email: string;
  createdAt: string;
}

export interface Conversation {
  id: string;
  title: string;
  systemPrompt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  conversationId: string;
  senderRole: 'user' | 'assistant' | 'system';
  content: string;
  memoryStatus: 'pending' | 'consolidated' | 'ignored';
  createdAt: string;
}
