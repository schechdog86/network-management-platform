import React from 'react';
import { ModernChatInterface } from '../components/Chat/ModernChatInterface';

const ChatPage: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-6 h-full">
      <div className="h-full max-h-[calc(100vh-200px)]">
        <ModernChatInterface className="h-full" />
      </div>
    </div>
  );
};

export default ChatPage;