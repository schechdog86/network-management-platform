import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, AlertCircle, Loader } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error';
  command?: {
    intent: string;
    entities: Record<string, any>;
    confidence: number;
  };
}

interface ChatInterfaceProps {
  className?: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '' }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { sendMessage, lastMessage, isConnected } = useWebSocket('/ws/chat');

  useEffect(() => {
    if (lastMessage) {
      const wsMessage = JSON.parse(lastMessage);
      if (wsMessage.type === 'chat_response') {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: wsMessage.data.content,
          timestamp: new Date(),
          command: wsMessage.data.command,
        }]);
        setIsProcessing(false);
      }
    }
  }, [lastMessage]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
      status: 'sending',
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    try {
      const response = await api.post('/api/v1/ai/chat', {
        message: userMessage.content,
        context: messages.slice(-10), // Send last 10 messages for context
      });

      if (response.data.command) {
        // Command was parsed and will be executed
        setMessages(prev => prev.map(msg => 
          msg.id === userMessage.id 
            ? { ...msg, status: 'sent', command: response.data.command }
            : msg
        ));
      } else {
        // Regular chat response
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: response.data.response,
          timestamp: new Date(),
        }]);
      }
    } catch (error) {
      setMessages(prev => prev.map(msg => 
        msg.id === userMessage.id 
          ? { ...msg, status: 'error' }
          : msg
      ));
      
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'system',
        content: 'Failed to process your request. Please try again.',
        timestamp: new Date(),
      }]);
    } finally {
      setIsProcessing(false);
      inputRef.current?.focus();
    }
  };

  const renderMessage = (message: Message) => {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';

    return (
      <div
        key={message.id}
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
      >
        <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} max-w-[80%]`}>
          <div className={`flex-shrink-0 ${isUser ? 'ml-3' : 'mr-3'}`}>
            {isUser ? (
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                <User className="w-5 h-5 text-white" />
              </div>
            ) : isSystem ? (
              <div className="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-white" />
              </div>
            ) : (
              <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
            )}
          </div>

          <div className={`
            px-4 py-2 rounded-lg 
            ${isUser ? 'bg-blue-500 text-white' : 
              isSystem ? 'bg-yellow-100 text-yellow-900 border border-yellow-300' : 
              'bg-gray-100 text-gray-900'}
          `}>
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            
            {message.command && (
              <div className="mt-2 pt-2 border-t border-gray-300">
                <p className="text-xs opacity-75">
                  Intent: {message.command.intent} ({Math.round(message.command.confidence * 100)}%)
                </p>
                {Object.keys(message.command.entities).length > 0 && (
                  <p className="text-xs opacity-75 mt-1">
                    Entities: {JSON.stringify(message.command.entities)}
                  </p>
                )}
              </div>
            )}

            {message.status === 'error' && (
              <p className="text-xs mt-1 text-red-200">Failed to send</p>
            )}

            <p className="text-xs mt-1 opacity-75">
              {new Date(message.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`flex flex-col h-full bg-white rounded-lg shadow-lg ${className}`}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-800">AI Assistant</h2>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <Bot className="w-16 h-16 mx-auto mb-4 text-gray-300" />
            <p>Hi! I'm your network management assistant.</p>
            <p className="text-sm mt-2">Ask me to help with network operations.</p>
            <div className="mt-4 text-xs text-gray-400">
              <p>Examples:</p>
              <p className="mt-1">"Show me all active servers"</p>
              <p>"Restart the web server on host 192.168.1.10"</p>
              <p>"Check disk usage on all systems"</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map(renderMessage)}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-6 py-4 border-t border-gray-200">
        <div className="flex items-center space-x-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isProcessing}
            placeholder="Type your command or question..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg 
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!input.trim() || isProcessing}
            className="p-2 bg-blue-500 text-white rounded-lg
                     hover:bg-blue-600 transition-colors
                     disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {isProcessing ? (
              <Loader className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
};