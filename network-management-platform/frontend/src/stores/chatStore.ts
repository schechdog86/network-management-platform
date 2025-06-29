import { create } from 'zustand';
import { api } from '../services/api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error' | 'thinking';
  command?: {
    intent: string;
    entities: Record<string, any>;
    confidence: number;
    executed?: boolean;
    result?: any;
  };
  metadata?: {
    tokens?: number;
    processingTime?: number;
    model?: string;
    sources?: string[];
  };
  feedback?: {
    helpful: boolean | null;
    comment?: string;
  };
}

export interface KnowledgeEntry {
  id: string;
  category: string;
  title: string;
  content: string;
  tags: string[];
  usageCount: number;
  lastUsed: Date;
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatSuggestion {
  text: string;
  category: 'command' | 'question' | 'action';
  icon?: string;
}

interface ChatState {
  messages: ChatMessage[];
  suggestions: ChatSuggestion[];
  knowledgeBase: KnowledgeEntry[];
  isTyping: boolean;
  isConnected: boolean;
  activeCommand: string | null;
  commandHistory: string[];
  preferences: {
    theme: 'light' | 'dark' | 'auto';
    fontSize: 'small' | 'medium' | 'large';
    showSuggestions: boolean;
    enableVoice: boolean;
    autoSave: boolean;
  };
  
  // Actions
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  deleteMessage: (id: string) => void;
  clearMessages: () => void;
  
  // Knowledge base actions
  addKnowledgeEntry: (entry: Omit<KnowledgeEntry, 'id' | 'createdAt' | 'updatedAt'>) => void;
  updateKnowledgeEntry: (id: string, updates: Partial<KnowledgeEntry>) => void;
  searchKnowledge: (query: string) => KnowledgeEntry[];
  
  // Chat actions
  sendMessage: (content: string) => Promise<void>;
  regenerateResponse: (messageId: string) => Promise<void>;
  provideFeedback: (messageId: string, helpful: boolean, comment?: string) => void;
  
  // Suggestions
  updateSuggestions: (suggestions: ChatSuggestion[]) => void;
  
  // Connection
  setConnectionStatus: (status: boolean) => void;
  setTypingStatus: (status: boolean) => void;
  
  // Preferences
  updatePreferences: (updates: Partial<ChatState['preferences']>) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  suggestions: [
    { text: "Show all active servers", category: "command", icon: "server" },
    { text: "Check system health", category: "command", icon: "heart" },
    { text: "What can you help me with?", category: "question", icon: "help" },
    { text: "Run network diagnostics", category: "action", icon: "activity" },
    { text: "Show recent alerts", category: "command", icon: "alert" },
  ],
  knowledgeBase: [
    {
      id: '1',
      category: 'network',
      title: 'Network Discovery',
      content: 'I can help you discover devices on your network using various protocols like SNMP, WMI, and ICMP.',
      tags: ['network', 'discovery', 'snmp', 'devices'],
      usageCount: 0,
      lastUsed: new Date(),
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    {
      id: '2',
      category: 'system',
      title: 'System Monitoring',
      content: 'I can monitor CPU, memory, disk usage, and other system metrics in real-time.',
      tags: ['system', 'monitoring', 'metrics', 'performance'],
      usageCount: 0,
      lastUsed: new Date(),
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    {
      id: '3',
      category: 'backup',
      title: 'Backup Management',
      content: 'I can help you create, schedule, and manage backups for your systems.',
      tags: ['backup', 'restore', 'scheduling', 'data'],
      usageCount: 0,
      lastUsed: new Date(),
      createdAt: new Date(),
      updatedAt: new Date(),
    },
  ],
  isTyping: false,
  isConnected: true,
  activeCommand: null,
  commandHistory: [],
  preferences: {
    theme: 'auto',
    fontSize: 'medium',
    showSuggestions: true,
    enableVoice: false,
    autoSave: true,
  },

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date(),
    }],
  })),

  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map(msg => 
      msg.id === id ? { ...msg, ...updates } : msg
    ),
  })),

  deleteMessage: (id) => set((state) => ({
    messages: state.messages.filter(msg => msg.id !== id),
  })),

  clearMessages: () => set({ messages: [] }),

  addKnowledgeEntry: (entry) => set((state) => ({
    knowledgeBase: [...state.knowledgeBase, {
      ...entry,
      id: Date.now().toString(),
      createdAt: new Date(),
      updatedAt: new Date(),
    }],
  })),

  updateKnowledgeEntry: (id, updates) => set((state) => ({
    knowledgeBase: state.knowledgeBase.map(entry => 
      entry.id === id 
        ? { ...entry, ...updates, updatedAt: new Date() } 
        : entry
    ),
  })),

  searchKnowledge: (query) => {
    const state = get();
    const queryLower = query.toLowerCase();
    
    return state.knowledgeBase.filter(entry => 
      entry.title.toLowerCase().includes(queryLower) ||
      entry.content.toLowerCase().includes(queryLower) ||
      entry.tags.some(tag => tag.toLowerCase().includes(queryLower))
    );
  },

  sendMessage: async (content) => {
    const { addMessage, updateMessage, addKnowledgeEntry } = get();
    
    // Add user message
    const userMessageId = Date.now().toString();
    addMessage({
      role: 'user',
      content,
      status: 'sent',
    });

    // Add assistant thinking message
    const assistantMessageId = (Date.now() + 1).toString();
    addMessage({
      role: 'assistant',
      content: '',
      status: 'thinking',
    });

    set({ isTyping: true });

    try {
      const response = await api.post('/api/v1/ai/chat', {
        message: content,
        context: get().messages.slice(-10),
        knowledgeBase: get().knowledgeBase.slice(0, 5),
      });

      const { data } = response;
      
      // Update assistant message with response
      updateMessage(assistantMessageId, {
        content: data.response,
        status: 'sent',
        command: data.command,
        metadata: {
          tokens: data.tokens,
          processingTime: data.processingTime,
          model: data.model,
          sources: data.sources,
        },
      });

      // Update command history if command was executed
      if (data.command) {
        set((state) => ({
          commandHistory: [...state.commandHistory, content].slice(-50),
        }));
      }

      // Auto-update knowledge base based on interaction
      if (data.learnedInfo) {
        addKnowledgeEntry({
          category: data.learnedInfo.category || 'general',
          title: data.learnedInfo.title,
          content: data.learnedInfo.content,
          tags: data.learnedInfo.tags || [],
          usageCount: 1,
          lastUsed: new Date(),
        });
      }

      // Update suggestions based on context
      if (data.suggestions) {
        set({ suggestions: data.suggestions });
      }

    } catch (error) {
      updateMessage(assistantMessageId, {
        content: 'I encountered an error processing your request. Please try again.',
        status: 'error',
      });
    } finally {
      set({ isTyping: false });
    }
  },

  regenerateResponse: async (messageId) => {
    const { messages, updateMessage } = get();
    const messageIndex = messages.findIndex(msg => msg.id === messageId);
    
    if (messageIndex === -1 || messageIndex === 0) return;
    
    const previousMessage = messages[messageIndex - 1];
    if (previousMessage.role !== 'user') return;

    updateMessage(messageId, { status: 'thinking', content: '' });
    set({ isTyping: true });

    try {
      const response = await api.post('/api/v1/ai/chat', {
        message: previousMessage.content,
        context: messages.slice(0, messageIndex - 1),
        regenerate: true,
      });

      updateMessage(messageId, {
        content: response.data.response,
        status: 'sent',
        command: response.data.command,
        metadata: response.data.metadata,
      });
    } catch (error) {
      updateMessage(messageId, {
        content: 'Failed to regenerate response. Please try again.',
        status: 'error',
      });
    } finally {
      set({ isTyping: false });
    }
  },

  provideFeedback: (messageId, helpful, comment) => {
    const { updateMessage } = get();
    updateMessage(messageId, {
      feedback: { helpful, comment },
    });
    
    // Send feedback to backend
    api.post('/api/v1/ai/feedback', {
      messageId,
      helpful,
      comment,
    }).catch(console.error);
  },

  updateSuggestions: (suggestions) => set({ suggestions }),

  setConnectionStatus: (status) => set({ isConnected: status }),
  
  setTypingStatus: (status) => set({ isTyping: status }),

  updatePreferences: (updates) => set((state) => ({
    preferences: { ...state.preferences, ...updates },
  })),
}));