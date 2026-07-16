import { useEffect, useState } from 'react';
import type { DocumentSection, WikiDocument } from '../../api/types';
import { useAppState } from '../../state/AppState';
import { fonts } from '../../theme/tokens';
import { documentStatusStyle } from '../../utils/statusStyle';
import { useHover } from '../../utils/useHover';
import { FlagBanner } from './FlagBanner';
import { SectionRenderer } from './SectionRenderer';
import { RelatedDocuments } from './RelatedDocuments';
import { HistoryTimeline } from './HistoryTimeline';
import { ReviewActionBar } from './ReviewActionBar';

export function ReviewScreen() {
  const {
    activeReviewDocument,
    activeSpaceData,
    closeReview,
    openReview,
    approveDocument,
    rejectDocument,
    reopenDocument,
    updateDocumentContent,
  } = useAppState();

  const [isEditing, setIsEditing] = useState(false);
  const [draftSections, setDraftSections] = useState<DocumentSection[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isRejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  useEffect(() => {
    setIsEditing(false);
    setRejecting(false);
    setReason('');
  }, [activeReviewDocument?.document_id]);

  if (!activeReviewDocument) return null;

  const doc = activeReviewDocument;
  const file = activeSpaceData.files.find((f) => f.file_id === doc.file_id);
  const badge = documentStatusStyle(doc.status);
  const relatedDocs = doc.related_document_ids
    .map((id) => activeSpaceData.documents.find((d) => d.document_id === id))
    .filter((d): d is WikiDocument => d !== undefined);

  const canEdit = doc.status === 'pending' || doc.status === 'rejected';

  function startEditing() {
    setDraftSections(doc.sections.map((s) => ({ ...s })));
    setIsEditing(true);
  }

  function cancelEditing() {
    setIsEditing(false);
  }

  async function saveEditing() {
    setIsSaving(true);
    try {
      await updateDocumentContent(doc.document_id, draftSections);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }

  function startReject() {
    setRejecting(true);
  }

  function cancelReject() {
    setRejecting(false);
    setReason('');
  }

  function confirmReject() {
    rejectDocument(doc.document_id, reason);
    setRejecting(false);
    setReason('');
  }

  const actionBarProps = {
    status: doc.status,
    canEdit,
    isEditing,
    isSaving,
    isRejecting,
    reason,
    onReasonChange: setReason,
    onStartReject: startReject,
    onCancelReject: cancelReject,
    onApprove: () => approveDocument(doc.document_id),
    onConfirmReject: confirmReject,
    onReopen: () => reopenDocument(doc.document_id),
    onClose: closeReview,
    onStartEdit: startEditing,
    onCancelEdit: cancelEditing,
    onSaveEdit: saveEditing,
  };

  return (
    <main
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        padding: '28px 36px',
        overflowY: 'auto',
      }}
    >
      <BackLink label={file?.name ?? ''} onClick={closeReview} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '18px 0 6px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: fonts.heading, fontWeight: 500, fontSize: 32, margin: 0 }}>{doc.title}</h1>
        <span style={{ fontFamily: fonts.mono, fontSize: 12, opacity: 0.5 }}>v{doc.version}</span>
        <span
          style={{
            fontSize: 11.5,
            padding: '4px 11px',
            borderRadius: 999,
            background: badge.background,
            color: badge.color,
          }}
        >
          {badge.label}
        </span>
        {isEditing && (
          <span style={{ fontSize: 11.5, opacity: 0.5, fontFamily: fonts.mono }}>수정 중</span>
        )}
      </div>

      <ReviewActionBar position="top" {...actionBarProps} />

      <div style={{ marginTop: 24 }}>
        <FlagBanner flags={doc.flags} />

        {(isEditing ? draftSections : doc.sections).map((section, i) => (
          <SectionRenderer
            key={i}
            section={section}
            isEditing={isEditing}
            onChange={(next) => setDraftSections((prev) => prev.map((s, idx) => (idx === i ? next : s)))}
          />
        ))}

        <RelatedDocuments relatedDocs={relatedDocs} onSelect={(id) => openReview(id)} />

        {doc.status === 'rejected' && (
          <div
            style={{
              marginBottom: 24,
              padding: '12px 16px',
              borderRadius: 10,
              background: 'rgba(178,90,62,0.12)',
              color: '#E08A6C',
              fontSize: 13,
            }}
          >
            반려 사유: {doc.reject_reason}
          </div>
        )}

        <HistoryTimeline history={doc.history} />
      </div>

      <ReviewActionBar position="bottom" {...actionBarProps} />
    </main>
  );
}

function BackLink({ label, onClick }: { label: string; onClick: () => void }) {
  const { isHovered, hoverProps } = useHover();
  return (
    <button
      onClick={onClick}
      {...hoverProps}
      style={{
        alignSelf: 'flex-start',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: 'none',
        border: 'none',
        fontSize: 13,
        opacity: isHovered ? 0.9 : 0.6,
        fontFamily: fonts.mono,
      }}
    >
      <span>← 목록으로</span>
      {label && <span>/ {label}</span>}
    </button>
  );
}
