import { useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../../api/types';
import { MessageBubble } from './MessageBubble';

interface ChatPanelProps {
  messages: ChatMessage[];
  titleForDocument: (documentId: string) => string;
  isSending: boolean;
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatPanel({ messages, titleForDocument, isSending, onSend, disabled }: ChatPanelProps) {
  const [draft, setDraft] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [messages, isSending]);

  function handleSend() {
    if (!draft.trim() || disabled) return;
    onSend(draft);
    setDraft('');
  }

  return (
    <div
      style={{
        height: 520,
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid rgba(var(--ink-rgb), 0.1)',
        borderRadius: 16,
        overflow: 'hidden',
      }}
    >
      <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && !isSending ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <p style={{ opacity: 0.5, fontSize: 13.5 }}>위키에 대해 궁금한 점을 물어보세요.</p>
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.message_id}
              message={message}
              sourceTitles={message.source_document_ids.map(titleForDocument)}
            />
          ))
        )}
        {isSending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, opacity: 0.6 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                border: '2px solid rgba(var(--ink-rgb), 0.2)',
                borderTopColor: 'var(--accent-text)',
                animation: 'spin 0.8s linear infinite',
                display: 'inline-block',
              }}
            />
            <span>위키를 참고하여 답변을 작성하고 있어요… </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: 12,
          borderTop: '1px solid rgba(var(--ink-rgb), 0.1)',
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={disabled}
          placeholder={disabled ? '승인된 문서가 있어야 질문할 수 있어요' : '질문을 입력하세요'}
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: 10,
            border: '1px solid rgba(var(--ink-rgb), 0.14)',
            background: 'transparent',
            color: 'var(--text)',
            fontSize: 13.5,
          }}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !draft.trim()}
          style={{
            padding: '10px 18px',
            borderRadius: 10,
            border: 'none',
            background: '#FF8A3D',
            color: '#0B0E13',
            fontWeight: 600,
            fontSize: 13.5,
            opacity: disabled || !draft.trim() ? 0.5 : 1,
          }}
        >
          전송
        </button>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
