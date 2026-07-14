import type { ChatMessage } from '../../api/types';
import { ChatMarkdown } from './ChatMarkdown';

interface MessageBubbleProps {
  message: ChatMessage;
  sourceTitles: string[];
}

export function MessageBubble({ message, sourceTitles }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: '72%' }}>
        <div
          className="chat-bubble-content"
          style={{
            padding: '10px 14px',
            borderRadius: 14,
            fontSize: 13.5,
            lineHeight: 1.55,
            background: isUser ? '#FF8A3D' : 'rgba(var(--ink-rgb), 0.06)',
            color: isUser ? '#0B0E13' : 'var(--text)',
          }}
        >
          <ChatMarkdown text={message.text} isUser={isUser} />
        </div>
        {sourceTitles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
            {sourceTitles.map((title) => (
              <span
                key={title}
                style={{
                  fontSize: 11,
                  padding: '3px 9px',
                  borderRadius: 999,
                  background: 'rgba(var(--ink-rgb), 0.06)',
                  opacity: 0.75,
                }}
              >
                📘 {title}
              </span>
            ))}
          </div>
        )}
      </div>
      <style>{`.chat-bubble-content > *:last-child { margin-bottom: 0; }`}</style>
    </div>
  );
}
