export interface FlatHeading {
  level: number;
  text: string;
  anchor: string;
  /** 1-indexed source line, used to match this heading to its rendered AST node. */
  line: number;
}

export interface HeadingNode extends FlatHeading {
  children: HeadingNode[];
}

const HEADING_LINE = /^(#{1,6})\s+(.+?)\s*#*\s*$/;
const FENCE_LINE = /^\s*(```|~~~)/;

export function stripHtmlComments(markdown: string): string {
  return markdown.replace(/<!--[\s\S]*?-->/g, '');
}

function stripInlineMarkdown(text: string): string {
  return text
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\*\*([^*]*)\*\*/g, '$1')
    .replace(/\*([^*]*)\*/g, '$1')
    .replace(/__([^_]*)__/g, '$1')
    .replace(/_([^_]*)_/g, '$1')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .trim();
}

/**
 * Extracts heading lines from markdown in document order, skipping fenced code blocks.
 * Anchors are positional (`${idPrefix}__h${index}`) rather than text-slugs so that
 * duplicate/Korean headings never collide. Each heading also records its source `line`
 * so MarkdownBody can look up the same anchor by AST node position instead of a
 * render-time counter (which React StrictMode's double-invoked renders would corrupt).
 */
export function extractHeadings(markdown: string, idPrefix: string): FlatHeading[] {
  const lines = stripHtmlComments(markdown).split('\n');
  const headings: FlatHeading[] = [];
  let inFence = false;
  let index = 0;

  lines.forEach((line, lineIdx) => {
    if (FENCE_LINE.test(line)) {
      inFence = !inFence;
      return;
    }
    if (inFence) return;

    const match = HEADING_LINE.exec(line);
    if (!match) return;

    const level = match[1].length;
    const text = stripInlineMarkdown(match[2]);
    if (!text) return;

    headings.push({ level, text, anchor: `${idPrefix}__h${index}`, line: lineIdx + 1 });
    index += 1;
  });

  return headings;
}

export function buildHeadingTree(flat: FlatHeading[]): HeadingNode[] {
  const root: HeadingNode[] = [];
  const stack: HeadingNode[] = [];

  for (const heading of flat) {
    const node: HeadingNode = { ...heading, children: [] };

    while (stack.length > 0 && stack[stack.length - 1].level >= node.level) {
      stack.pop();
    }

    if (stack.length === 0) {
      root.push(node);
    } else {
      stack[stack.length - 1].children.push(node);
    }

    stack.push(node);
  }

  return root;
}

export interface DedupedTree {
  tree: HeadingNode[];
  /** Anchor of the removed root heading, if any — still rendered in the body, so the
   * scroll position tracker needs to map it back to the doc-level TOC row. */
  removedAnchor?: string;
}

/**
 * A document's own top-level heading (e.g. `# SQL_plan_manager`) usually repeats the
 * document title already shown above the tree (📖 doc.title). Drop that redundant root
 * node and promote its children, so the same text doesn't appear twice in the TOC.
 */
export function dedupeTitleHeading(tree: HeadingNode[], title: string): DedupedTree {
  if (tree.length > 0 && tree[0].text.trim() === title.trim()) {
    return { tree: tree[0].children, removedAnchor: tree[0].anchor };
  }
  return { tree };
}
