import { useEffect, useRef } from 'react';
import type { HeadingNode } from '../../utils/markdownHeadings';
import { useHover } from '../../utils/useHover';
import { fonts } from '../../theme/tokens';

export interface WikiTocDoc {
  documentId: string;
  title: string;
  anchor: string;
  children: HeadingNode[];
}

function scrollToAnchor(anchor: string) {
  document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function TocRow({
  label,
  indent,
  onClick,
  isDocTitle,
  isActive,
  anchor,
}: {
  label: string;
  indent: number;
  onClick: () => void;
  isDocTitle?: boolean;
  isActive?: boolean;
  anchor: string;
}) {
  const { isHovered, hoverProps } = useHover();
  return (
    <button
      onClick={onClick}
      data-anchor={anchor}
      {...hoverProps}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        border: 'none',
        borderLeft: isActive ? '3px solid var(--accent-text)' : '3px solid transparent',
        background: isActive ? 'rgba(255,138,61,0.08)' : isHovered ? 'rgba(var(--ink-rgb), 0.05)' : 'transparent',
        padding: '5px 8px',
        paddingLeft: 5 + indent * 14,
        borderRadius: 6,
        fontSize: isDocTitle ? 15 : 13,
        fontWeight: isDocTitle ? 600 : isActive ? 600 : 500,
        fontFamily: isDocTitle ? fonts.heading : fonts.body,
        color: isActive || isHovered ? 'var(--accent-text)' : 'var(--text)',
        opacity: isDocTitle || isActive ? 1 : 0.75,
      }}
    >
      {label}
    </button>
  );
}

function HeadingRows({ nodes, depth, activeAnchor }: { nodes: HeadingNode[]; depth: number; activeAnchor?: string }) {
  return (
    <>
      {nodes.map((node) => (
        <div key={node.anchor}>
          <TocRow
            label={node.text}
            indent={depth}
            onClick={() => scrollToAnchor(node.anchor)}
            isActive={node.anchor === activeAnchor}
            anchor={node.anchor}
          />
          {node.children.length > 0 && (
            <HeadingRows nodes={node.children} depth={depth + 1} activeAnchor={activeAnchor} />
          )}
        </div>
      ))}
    </>
  );
}

export function WikiTocTree({ docs, activeAnchor }: { docs: WikiTocDoc[]; activeAnchor?: string }) {
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!activeAnchor || !navRef.current) return;
    const row = navRef.current.querySelector(`[data-anchor="${CSS.escape(activeAnchor)}"]`);
    row?.scrollIntoView({ block: 'nearest' });
  }, [activeAnchor]);

  return (
    <nav
      ref={navRef}
      style={{
        width: 260,
        flexShrink: 0,
        height: '100%',
        overflowY: 'auto',
        paddingRight: 12,
      }}
    >
      {docs.map((doc) => (
        <div key={doc.documentId} style={{ marginBottom: 14 }}>
          <TocRow
            label={`📖 ${doc.title}`}
            indent={0}
            onClick={() => scrollToAnchor(doc.anchor)}
            isDocTitle
            isActive={doc.anchor === activeAnchor}
            anchor={doc.anchor}
          />
          <HeadingRows nodes={doc.children} depth={1} activeAnchor={activeAnchor} />
        </div>
      ))}
    </nav>
  );
}
