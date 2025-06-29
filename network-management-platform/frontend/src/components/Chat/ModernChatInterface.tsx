import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Send, Bot, User, AlertCircle, Loader, RefreshCw, 
  ThumbsUp, ThumbsDown, Copy, Check, Sparkles, 
  Mic, MicOff, Settings, BookOpen, Command,
  ChevronDown, ChevronUp, MessageSquare, HelpCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatStore } from '../../stores/chatStore';
import { ChatMessage } from '../../stores/chatStore';

interface ModernChatInterfaceProps {
  className?: string;
}

export const ModernChatInterface: React.FC<ModernChatInterfaceProps> = ({ className = '' }) => {
  const {
    messages,
    suggestions,
    knowledgeBase,
    isTyping,
    isConnected,
    preferences,
    sendMessage,
    regenerateResponse,
    provideFeedback,
  } = useChatStore();

  const [input, setInput] = useState('');
  const [showSuggestions] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    
    await sendMessage(input.trim());
    setInput('');
    inputRef.current?.focus();
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    inputRef.current?.focus();
  };

  const copyToClipboard = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const toggleMessageExpansion = (id: string) => {
    setExpandedMessages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const renderMessage = (message: ChatMessage, index: number) => {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';
    const isExpanded = expandedMessages.has(message.id);
    const hasMetadata = message.metadata && Object.keys(message.metadata).length > 0;

    return (
      <motion.div
        key={message.id}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: index * 0.05 }}
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}
      >
        <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} max-w-[85%]`}>
          {/* Avatar */}
          <div className={`flex-shrink-0 ${isUser ? 'ml-3' : 'mr-3'}`}>
            <div className={`
              w-10 h-10 rounded-full flex items-center justify-center shadow-lg
              ${isUser ? 'bg-gradient-to-br from-blue-500 to-blue-600' : 
                isSystem ? 'bg-gradient-to-br from-yellow-500 to-orange-500' : 
                'bg-gradient-to-br from-green-500 to-emerald-600'}
            `}>
              {isUser ? (
                <User className="w-6 h-6 text-white" />
              ) : isSystem ? (
                <AlertCircle className="w-6 h-6 text-white" />
              ) : (
                <Bot className="w-6 h-6 text-white" />
              )}
            </div>
          </div>

          {/* Message Content */}
          <div className="flex flex-col space-y-2">
            <div className={`
              px-5 py-3 rounded-2xl shadow-sm relative
              ${isUser ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white' : 
                isSystem ? 'bg-yellow-50 text-yellow-900 border border-yellow-200' : 
                'bg-white text-gray-800 border border-gray-100'}
            `}>
              {/* Status indicator for thinking */}
              {message.status === 'thinking' && (
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 animate-pulse" />
                  <span className="text-sm">Thinking...</span>
                  <Loader className="w-4 h-4 animate-spin" />
                </div>
              )}

              {/* Main content */}
              {message.content && (
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {message.content}
                </p>
              )}

              {/* Command info */}
              {message.command && (
                <div className={`
                  mt-3 pt-3 border-t text-xs
                  ${isUser ? 'border-blue-400 text-blue-100' : 'border-gray-200 text-gray-600'}
                `}>
                  <div className="flex items-center space-x-2 mb-1">
                    <Command className="w-3 h-3" />
                    <span className="font-semibold">Command detected:</span>
                  </div>
                  <div className="ml-5 space-y-1">
                    <p>Intent: {message.command.intent} ({Math.round(message.command.confidence * 100)}%)</p>
                    {Object.keys(message.command.entities).length > 0 && (
                      <p>Entities: {JSON.stringify(message.command.entities, null, 2)}</p>
                    )}
                    {message.command.executed && (
                      <p className="text-green-600">✓ Executed successfully</p>
                    )}
                  </div>
                </div>
              )}

              {/* Metadata expansion */}
              {hasMetadata && (
                <button
                  onClick={() => toggleMessageExpansion(message.id)}
                  className={`
                    mt-2 text-xs flex items-center space-x-1
                    ${isUser ? 'text-blue-200 hover:text-white' : 'text-gray-500 hover:text-gray-700'}
                  `}
                >
                  {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  <span>Details</span>
                </button>
              )}

              {/* Expanded metadata */}
              <AnimatePresence>
                {isExpanded && hasMetadata && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className={`
                      mt-2 pt-2 border-t text-xs overflow-hidden
                      ${isUser ? 'border-blue-400 text-blue-100' : 'border-gray-200 text-gray-600'}
                    `}
                  >
                    {message.metadata?.tokens && <p>Tokens: {message.metadata.tokens}</p>}
                    {message.metadata?.processingTime && <p>Processing: {message.metadata.processingTime}ms</p>}
                    {message.metadata?.model && <p>Model: {message.metadata.model}</p>}
                    {message.metadata?.sources && message.metadata.sources.length > 0 && (
                      <div className="mt-1">
                        <p>Sources:</p>
                        <ul className="ml-3">
                          {message.metadata.sources.map((source, i) => (
                            <li key={i}>• {source}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Action buttons */}
            {!isUser && message.content && message.status === 'sent' && (
              <div className="flex items-center space-x-2 ml-2">
                {/* Copy button */}
                <button
                  onClick={() => copyToClipboard(message.content, message.id)}
                  className="p-1.5 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                  title="Copy message"
                >
                  {copiedId === message.id ? (
                    <Check className="w-4 h-4 text-green-600" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </button>

                {/* Regenerate button */}
                <button
                  onClick={() => regenerateResponse(message.id)}
                  className="p-1.5 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                  title="Regenerate response"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>

                {/* Feedback buttons */}
                <button
                  onClick={() => provideFeedback(message.id, true)}
                  className={`p-1.5 rounded-lg transition-colors ${
                    message.feedback?.helpful === true
                      ? 'text-green-600 bg-green-50'
                      : 'text-gray-500 hover:text-green-600 hover:bg-green-50'
                  }`}
                  title="Helpful"
                >
                  <ThumbsUp className="w-4 h-4" />
                </button>

                <button
                  onClick={() => provideFeedback(message.id, false)}
                  className={`p-1.5 rounded-lg transition-colors ${
                    message.feedback?.helpful === false
                      ? 'text-red-600 bg-red-50'
                      : 'text-gray-500 hover:text-red-600 hover:bg-red-50'
                  }`}
                  title="Not helpful"
                >
                  <ThumbsDown className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Timestamp */}
            <p className={`text-xs ml-2 ${isUser ? 'text-blue-100' : 'text-gray-500'}`}>
              {new Date(message.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <div className={`flex flex-col h-full bg-gray-50 rounded-xl shadow-xl overflow-hidden ${className}`}>
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-800">AI Assistant</h2>
              <div className="flex items-center space-x-2 text-sm">
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-gray-600">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
          
          {/* Header actions */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowKnowledge(!showKnowledge)}
              className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              title="Knowledge Base"
            >
              <BookOpen className="w-5 h-5" />
            </button>
            <button
              className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="p-4 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full mb-6">
              <Bot className="w-16 h-16 text-white" />
            </div>
            <h3 className="text-2xl font-semibold text-gray-800 mb-2">
              Hi! I'm your Network Management Assistant
            </h3>
            <p className="text-gray-600 max-w-md mb-8">
              I can help you monitor systems, manage networks, run diagnostics, and automate tasks. 
              Just ask me anything or choose from the suggestions below.
            </p>
            
            {/* Quick actions */}
            <div className="grid grid-cols-2 gap-3 max-w-lg">
              {suggestions.slice(0, 4).map((suggestion, index) => (
                <button
                  key={index}
                  onClick={() => handleSuggestionClick(suggestion.text)}
                  className="p-3 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 
                           hover:border-blue-500 hover:text-blue-600 transition-colors text-left"
                >
                  <HelpCircle className="w-4 h-4 mb-1 text-blue-500" />
                  {suggestion.text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map(renderMessage)}
            {isTyping && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center space-x-2 text-gray-500"
              >
                <Bot className="w-5 h-5" />
                <span className="text-sm">AI is typing</span>
                <Loader className="w-4 h-4 animate-spin" />
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Suggestions bar */}
      <AnimatePresence>
        {showSuggestions && preferences.showSuggestions && suggestions.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="px-6 py-3 bg-white border-t border-gray-100"
          >
            <div className="flex items-start space-x-2 overflow-x-auto pb-2">
              <Sparkles className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
              {suggestions.map((suggestion, index) => (
                <button
                  key={index}
                  onClick={() => handleSuggestionClick(suggestion.text)}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm 
                           text-gray-700 whitespace-nowrap transition-colors flex-shrink-0"
                >
                  {suggestion.text}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="px-6 py-4 bg-white border-t border-gray-200">
        <div className="flex items-end space-x-3">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              disabled={isTyping}
              placeholder="Type your message or command..."
              rows={1}
              className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl resize-none
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       disabled:bg-gray-100 disabled:cursor-not-allowed"
              style={{ maxHeight: '150px' }}
            />
            
            {/* Voice input button */}
            {preferences.enableVoice && (
              <button
                type="button"
                onClick={() => setIsRecording(!isRecording)}
                className={`absolute right-3 bottom-3 p-2 rounded-lg transition-colors ${
                  isRecording 
                    ? 'bg-red-500 text-white' 
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                {isRecording ? (
                  <MicOff className="w-4 h-4" />
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </button>
            )}
          </div>
          
          <button
            type="submit"
            disabled={!input.trim() || isTyping}
            className="p-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl
                     hover:from-blue-600 hover:to-blue-700 transition-all transform
                     disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
                     hover:scale-105 active:scale-95"
          >
            {isTyping ? (
              <Loader className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </form>

      {/* Knowledge Base Sidebar */}
      <AnimatePresence>
        {showKnowledge && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            className="absolute right-0 top-0 h-full w-80 bg-white shadow-xl border-l border-gray-200 z-50"
          >
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Knowledge Base</h3>
                <button
                  onClick={() => setShowKnowledge(false)}
                  className="p-1 hover:bg-gray-100 rounded-lg"
                >
                  <ChevronDown className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="p-4 overflow-y-auto h-full">
              {knowledgeBase.map((entry) => (
                <div key={entry.id} className="mb-4 p-3 bg-gray-50 rounded-lg">
                  <h4 className="font-medium text-sm mb-1">{entry.title}</h4>
                  <p className="text-xs text-gray-600 mb-2">{entry.content}</p>
                  <div className="flex flex-wrap gap-1">
                    {entry.tags.map((tag, i) => (
                      <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};