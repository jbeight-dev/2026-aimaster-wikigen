import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fonts, radii } from '../../theme/tokens';
import { stripHtmlComments, type FlatHeading } from '../../utils/markdownHeadings';

// 모듈 스코프 상수로 고정 — 매 렌더마다 새 배열을 넘기면 ReactMarkdown이 내부 프로세서를 다시 만든다.
const REMARK_PLUGINS = [remarkGfm];

/**
 * Looks up a heading's anchor by its source line rather than a render-order counter.
 * A counter would double-count under React StrictMode, which invokes each of these
 * inline heading components twice per commit and corrupts any shared mutable state.
 * `node.position.start.line` is stable across both invocations of the same node, so
 * a pure lookup keeps the id consistent with the anchors used by the left-nav TOC.
 */
function createComponents(headingsByLine?: Map<number, string>): Components {
  const idFor = (line: number | undefined) => (line !== undefined ? headingsByLine?.get(line) : undefined);

  return {
  h1: ({ node, children }) => (
    <h1 id={idFor(node?.position?.start.line)} style={{ fontFamily: fonts.heading, fontWeight: 500, fontSize: 22, margin: '18px 0 10px' }}>{children}</h1>
  ),
  h2: ({ node, children }) => (
    <h2 id={idFor(node?.position?.start.line)} style={{ fontFamily: fonts.heading, fontWeight: 500, fontSize: 18, margin: '16px 0 8px' }}>{children}</h2>
  ),
  h3: ({ node, children }) => (
    <h3 id={idFor(node?.position?.start.line)} style={{ fontFamily: fonts.body, fontSize: 15, fontWeight: 600, margin: '14px 0 6px' }}>{children}</h3>
  ),
  h4: ({ node, children }) => <h4 id={idFor(node?.position?.start.line)} style={{ fontFamily: fonts.body, fontSize: 14, fontWeight: 600, margin: '12px 0 6px' }}>{children}</h4>,
  h5: ({ node, children }) => <h5 id={idFor(node?.position?.start.line)} style={{ fontFamily: fonts.body, fontSize: 13.5, fontWeight: 600, margin: '10px 0 6px' }}>{children}</h5>,
  h6: ({ node, children }) => <h6 id={idFor(node?.position?.start.line)} style={{ fontFamily: fonts.body, fontSize: 13, fontWeight: 600, margin: '10px 0 6px' }}>{children}</h6>,
  p: ({ children }) => (
    <p style={{ fontFamily: fonts.body, margin: '0 0 10px', fontSize: 14, lineHeight: 1.65, opacity: 0.85 }}>{children}</p>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-text)' }}>
      {children}
    </a>
  ),
  ul: ({ children }) => <ul style={{ fontFamily: fonts.body, margin: '0 0 10px', paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ fontFamily: fonts.body, margin: '0 0 10px', paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>{children}</ol>,
  li: ({ children }) => <li style={{ marginBottom: 4, opacity: 0.85 }}>{children}</li>,
  blockquote: ({ children }) => (
    <blockquote
      style={{
        fontFamily: fonts.body,
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
}

export function MarkdownBody({ content, headings }: { content: string; headings?: FlatHeading[] }) {
  // components 객체를 매 렌더마다 새로 만들면 React가 h1~h6를 "다른 타입"으로 보고 통째로
  // 재마운트한다. 이 파일을 쓰는 SpaceWikiView는 스크롤할 때마다 재렌더되므로, 재마운트가
  // 일어나면 스크롤 위치 추적용으로 잡아둔 heading 엘리먼트 참조가 즉시 detached 상태가 되어
  // 위치 계산이 깨진다. headings가 바뀌지 않는 한 components 참조를 고정해 재마운트를 막는다.
  const headingsByLine = useMemo(
    () => headings && new Map(headings.map((h) => [h.line, h.anchor])),
    [headings],
  );
  const components = useMemo(() => createComponents(headingsByLine), [headingsByLine]);

  return (
    <div style={{ color: 'var(--text)' }}>
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={components}>
        {stripHtmlComments(content)}
      </ReactMarkdown>
    </div>
  );
}
