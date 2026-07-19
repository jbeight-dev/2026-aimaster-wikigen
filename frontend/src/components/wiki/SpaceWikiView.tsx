import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useAppState } from '../../state/AppState';
import type { WikiDocument } from '../../api/types';
import { MarkdownBody } from '../review/MarkdownBody';
import { buildHeadingTree, dedupeTitleHeading, extractHeadings } from '../../utils/markdownHeadings';
import { WikiTocTree, type WikiTocDoc } from './WikiTocTree';

// SpaceMain의 padding-bottom(28px)만큼 하단 여백을 남겨, 이 영역이 main의 스크롤을 유발하지 않도록 한다.
const MAIN_BOTTOM_PADDING = 28;

function getMarkdownContent(doc: WikiDocument): string {
  return doc.sections
    .filter((section) => section.type === 'markdown')
    .map((section) => section.content)
    .join('\n\n');
}

export function SpaceWikiView() {
  const { activeSpaceData, setActiveTab } = useAppState();
  const documents = activeSpaceData.documents;

  const docEntries = useMemo(() => {
    const approvedDocs = documents.filter((doc) => doc.status === 'approved');
    return approvedDocs.map((doc) => {
      const markdown = getMarkdownContent(doc);
      const headings = extractHeadings(markdown, doc.document_id);
      return {
        doc,
        markdown,
        headings,
        tree: buildHeadingTree(headings),
      };
    });
  }, [documents]);

  // 문서의 최상위 heading이 doc.title과 중복돼 트리에서 제거된 경우(dedupeTitleHeading),
  // 본문에는 여전히 그 heading이 렌더링되므로 스크롤 추적이 그 anchor를 가리킬 수 있다.
  // 그 anchor를 문서 그룹 행(doc-${document_id})으로 리다이렉트해 강조 표시가 항상 트리의
  // 실제 행과 맞아떨어지도록 한다.
  const { tocDocs, activeAnchorRedirect } = useMemo(() => {
    const redirect = new Map<string, string>();
    const docs: WikiTocDoc[] = docEntries.map(({ doc, tree }) => {
      const deduped = dedupeTitleHeading(tree, doc.title);
      const anchor = `doc-${doc.document_id}`;
      if (deduped.removedAnchor) {
        redirect.set(deduped.removedAnchor, anchor);
      }
      return {
        documentId: doc.document_id,
        title: doc.title,
        anchor,
        children: deduped.tree,
      };
    });
    return { tocDocs: docs, activeAnchorRedirect: redirect };
  }, [docEntries]);

  const rowRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [availableHeight, setAvailableHeight] = useState<number>();
  const [activeAnchor, setActiveAnchor] = useState<string>();

  // 좌측 트리/가운데 본문이 페이지 스크롤과 분리되어 각자 스크롤되도록, 뷰포트에서 남은 높이를 측정한다.
  useLayoutEffect(() => {
    function updateHeight() {
      if (!rowRef.current) return;
      const top = rowRef.current.getBoundingClientRect().top;
      setAvailableHeight(window.innerHeight - top - MAIN_BOTTOM_PADDING);
    }
    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, [docEntries.length]);

  // 가운데 본문에서 현재 읽고 있는 heading을 좌측 트리에 강조 표시한다.
  // IntersectionObserver의 threshold 교차 이벤트 방식은 heading 사이 간격이 넓으면(긴 문단)
  // 어떤 heading도 교차 지점을 지나지 않는 구간이 생겨 activeAnchor가 갱신되지 않는 문제가 있어,
  // 매 스크롤마다 "본문 상단 기준선보다 위에 있는 마지막 heading"을 직접 계산하는 방식을 쓴다.
  useEffect(() => {
    const container = contentRef.current;
    if (!container) return;
    const headingEls = Array.from(
      container.querySelectorAll<HTMLElement>('h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]'),
    );
    if (headingEls.length === 0) return;

    const THRESHOLD_OFFSET = 80;
    let ticking = false;

    function updateActive() {
      ticking = false;
      const thresholdY = container!.getBoundingClientRect().top + THRESHOLD_OFFSET;
      let current = headingEls[0].id;
      for (const el of headingEls) {
        if (el.getBoundingClientRect().top <= thresholdY) {
          current = el.id;
        } else {
          break;
        }
      }
      setActiveAnchor(activeAnchorRedirect.get(current) ?? current);
    }

    function onScroll() {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(updateActive);
      }
    }

    updateActive();
    container.addEventListener('scroll', onScroll);
    return () => container.removeEventListener('scroll', onScroll);
  }, [docEntries, activeAnchorRedirect]);

  if (docEntries.length === 0) {
    return (
      <div
        style={{
          border: '1px dashed rgba(var(--ink-rgb), 0.2)',
          borderRadius: 14,
          padding: '40px 24px',
          textAlign: 'center',
        }}
      >
        <p style={{ margin: '0 0 16px', fontSize: 13.5, opacity: 0.65 }}>
          아직 승인된 문서가 없어요. 문서를 등록하고 검토를 완료해보세요.
        </p>
        <button
          onClick={() => setActiveTab('upload')}
          style={{
            padding: '9px 18px',
            borderRadius: 999,
            border: '1px solid rgba(var(--ink-rgb), 0.18)',
            background: 'transparent',
            color: 'var(--text)',
            fontSize: 13,
          }}
        >
          문서 등록으로 이동
        </button>
      </div>
    );
  }

  return (
    <div ref={rowRef} style={{ display: 'flex', gap: 32, height: availableHeight }}>
      <WikiTocTree docs={tocDocs} activeAnchor={activeAnchor} />
      <div ref={contentRef} style={{ flex: 1, minWidth: 0, maxWidth: 1000, overflowY: 'auto' }}>
        {docEntries.map(({ doc, markdown, headings }, i) => (
          <div key={doc.document_id} id={`doc-${doc.document_id}`}>
            {i > 0 && (
              <hr style={{ border: 'none', borderTop: '1px solid rgba(var(--ink-rgb), 0.12)', margin: '32px 0' }} />
            )}
            <MarkdownBody content={markdown} headings={headings} />
          </div>
        ))}
      </div>
    </div>
  );
}
