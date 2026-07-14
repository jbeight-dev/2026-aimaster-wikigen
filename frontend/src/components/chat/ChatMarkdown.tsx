import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fonts, radii } from '../../theme/tokens';

function buildComponents(isUser: boolean): Components {
  const codeBg = isUser ? 'rgba(11, 14, 19, 0.12)' : 'rgba(var(--ink-rgb), 0.08)';

  return {
    p: ({ children }) => <p style={{ margin: '0 0 8px', lineHeight: 1.55 }}>{children}</p>,
    strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
    a: ({ children, href }) => (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        style={{ color: isUser ? '#0B0E13' : 'var(--accent-text)', textDecoration: 'underline' }}
      >
        {children}
      </a>
    ),
    ul: ({ children }) => <ul style={{ margin: '0 0 8px', paddingLeft: 18, lineHeight: 1.55 }}>{children}</ul>,
    ol: ({ children }) => <ol style={{ margin: '0 0 8px', paddingLeft: 18, lineHeight: 1.55 }}>{children}</ol>,
    li: ({ children }) => <li style={{ marginBottom: 3 }}>{children}</li>,
    h1: ({ children }) => <div style={{ fontSize: 15, fontWeight: 700, margin: '4px 0 6px' }}>{children}</div>,
    h2: ({ children }) => <div style={{ fontSize: 14.5, fontWeight: 700, margin: '4px 0 6px' }}>{children}</div>,
    h3: ({ children }) => <div style={{ fontSize: 14, fontWeight: 700, margin: '4px 0 6px' }}>{children}</div>,
    blockquote: ({ children }) => (
      <blockquote
        style={{
          margin: '0 0 8px',
          padding: '2px 10px',
          borderLeft: `2px solid ${isUser ? 'rgba(11, 14, 19, 0.3)' : 'rgba(var(--ink-rgb), 0.25)'}`,
          opacity: 0.85,
        }}
      >
        {children}
      </blockquote>
    ),
    code: ({ className, children }) => {
      const isBlock = Boolean(className);
      return (
        <code
          style={{
            fontFamily: fonts.mono,
            fontSize: 12,
            background: isBlock ? 'transparent' : codeBg,
            padding: isBlock ? 0 : '1px 5px',
            borderRadius: 4,
          }}
        >
          {children}
        </code>
      );
    },
    pre: ({ children }) => (
      <pre
        style={{
          margin: '0 0 8px',
          padding: '10px 12px',
          borderRadius: radii.sm,
          background: codeBg,
          overflowX: 'auto',
          whiteSpace: 'pre',
        }}
      >
        {children}
      </pre>
    ),
    hr: () => (
      <hr
        style={{
          border: 'none',
          borderTop: `1px solid ${isUser ? 'rgba(11, 14, 19, 0.2)' : 'rgba(var(--ink-rgb), 0.14)'}`,
          margin: '8px 0',
        }}
      />
    ),
    table: ({ children }) => (
      <div style={{ overflowX: 'auto', marginBottom: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th
        style={{
          textAlign: 'left',
          padding: '5px 8px',
          borderBottom: `1px solid ${isUser ? 'rgba(11, 14, 19, 0.2)' : 'rgba(var(--ink-rgb), 0.14)'}`,
          fontSize: 11,
          opacity: 0.75,
        }}
      >
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td
        style={{
          padding: '5px 8px',
          borderBottom: `1px solid ${isUser ? 'rgba(11, 14, 19, 0.1)' : 'rgba(var(--ink-rgb), 0.06)'}`,
        }}
      >
        {children}
      </td>
    ),
  };
}

export function ChatMarkdown({ text, isUser }: { text: string; isUser: boolean }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={buildComponents(isUser)}>
      {text}
    </ReactMarkdown>
  );
}
