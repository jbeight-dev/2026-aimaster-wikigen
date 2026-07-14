import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fonts, radii } from '../../theme/tokens';

const components: Components = {
  h1: ({ children }) => (
    <h1 style={{ fontFamily: fonts.heading, fontWeight: 500, fontSize: 22, margin: '18px 0 10px' }}>{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 style={{ fontFamily: fonts.heading, fontWeight: 500, fontSize: 18, margin: '16px 0 8px' }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{ fontSize: 15, fontWeight: 600, margin: '14px 0 6px' }}>{children}</h3>
  ),
  h4: ({ children }) => <h4 style={{ fontSize: 14, fontWeight: 600, margin: '12px 0 6px' }}>{children}</h4>,
  h5: ({ children }) => <h5 style={{ fontSize: 13.5, fontWeight: 600, margin: '10px 0 6px' }}>{children}</h5>,
  h6: ({ children }) => <h6 style={{ fontSize: 13, fontWeight: 600, margin: '10px 0 6px' }}>{children}</h6>,
  p: ({ children }) => (
    <p style={{ margin: '0 0 10px', fontSize: 14, lineHeight: 1.65, opacity: 0.85 }}>{children}</p>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-text)' }}>
      {children}
    </a>
  ),
  ul: ({ children }) => <ul style={{ margin: '0 0 10px', paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ margin: '0 0 10px', paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>{children}</ol>,
  li: ({ children }) => <li style={{ marginBottom: 4, opacity: 0.85 }}>{children}</li>,
  blockquote: ({ children }) => (
    <blockquote
      style={{
        margin: '0 0 10px',
        padding: '4px 12px',
        borderLeft: '3px solid rgba(var(--ink-rgb), 0.2)',
        opacity: 0.75,
        fontSize: 14,
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
          fontSize: isBlock ? 12.5 : 12.5,
          background: isBlock ? 'transparent' : 'rgba(var(--ink-rgb), 0.08)',
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
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        background: 'rgba(var(--ink-rgb), 0.04)',
        borderRadius: radii.sm,
        padding: '10px 12px',
        marginBottom: 10,
      }}
    >
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div style={{ overflowX: 'auto', marginBottom: 10 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th
      style={{
        textAlign: 'left',
        padding: '8px 10px',
        borderBottom: '1px solid rgba(var(--ink-rgb), 0.14)',
        fontFamily: fonts.mono,
        fontSize: 11.5,
        textTransform: 'uppercase',
        opacity: 0.6,
      }}
    >
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td style={{ padding: '8px 10px', borderBottom: '1px solid rgba(var(--ink-rgb), 0.06)' }}>{children}</td>
  ),
  hr: () => <hr style={{ border: 'none', borderTop: '1px solid rgba(var(--ink-rgb), 0.12)', margin: '14px 0' }} />,
};

function stripHtmlComments(content: string): string {
  return content.replace(/<!--[\s\S]*?-->/g, '');
}

export function MarkdownBody({ content }: { content: string }) {
  return (
    <div style={{ color: 'var(--text)' }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {stripHtmlComments(content)}
      </ReactMarkdown>
    </div>
  );
}
