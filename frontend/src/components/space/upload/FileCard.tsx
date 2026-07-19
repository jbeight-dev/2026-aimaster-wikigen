import type { UploadedFile, WikiDocument } from '../../../api/types';
import { formatBytes } from '../../../utils/format';
import { useHover } from '../../../utils/useHover';
import { DocumentRow } from './DocumentRow';

interface FileCardProps {
  file: UploadedFile;
  documents: WikiDocument[];
  onAnalyze: () => void;
  onRetry: () => void;
  onDelete: () => void;
  onOpenReview: (documentId: string) => void;
}

export function FileCard({ file, documents, onAnalyze, onRetry, onDelete, onOpenReview }: FileCardProps) {
  return (
    <div
      style={{
        border: '1px solid rgba(var(--ink-rgb), 0.1)',
        borderRadius: 12,
        padding: '14px 16px',
        marginBottom: 8,
        background: 'rgba(var(--ink-rgb), 0.02)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <span style={{ fontSize: 18, flexShrink: 0 }}>📄</span>
          <span style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {file.name}
          </span>
          <span style={{ fontSize: 12, opacity: 0.5, flexShrink: 0 }}>{formatBytes(file.size_bytes)}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <StatusAction file={file} onAnalyze={onAnalyze} onRetry={onRetry} />
          <DeleteButton onClick={onDelete} />
        </div>
      </div>

      {file.status === 'analyzing' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12.5, opacity: 0.75 }}>
          <Spinner />
          <span>{file.step_message}</span>
        </div>
      )}

      {(file.status === 'analysis_failed' || file.status === 'upload_failed') && (
        <div
          style={{
            marginTop: 10,
            padding: '9px 12px',
            borderRadius: 8,
            background: 'rgba(178,90,62,0.12)',
            color: '#E08A6C',
            fontSize: 12.5,
          }}
        >
          ⚠ {file.status === 'upload_failed' ? '지원하지 않는 파일 형식이에요.' : '분석 중 오류가 발생했어요.'}
        </div>
      )}

      {file.status === 'done' && documents.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {documents.map((doc) => (
            <DocumentRow key={doc.document_id} doc={doc} onOpenReview={() => onOpenReview(doc.document_id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatusAction({
  file,
  onAnalyze,
  onRetry,
}: {
  file: UploadedFile;
  onAnalyze: () => void;
  onRetry: () => void;
}) {
  const { isHovered, hoverProps } = useHover();

  if (file.status === 'uploaded') {
    return (
      <button
        onClick={onAnalyze}
        {...hoverProps}
        style={{
          fontSize: 12.5,
          fontWeight: 600,
          padding: '7px 14px',
          borderRadius: 999,
          border: 'none',
          background: isHovered ? '#ff9a56' : '#FF8A3D',
          color: '#0B0E13',
        }}
      >
        분석시작
      </button>
    );
  }
  if (file.status === 'done') {
    return (
      <span
        style={{
          fontSize: 12,
          padding: '5px 11px',
          borderRadius: 999,
          background: 'rgba(255,138,61,0.14)',
          color: 'var(--accent-text)',
        }}
      >
        분석완료
      </span>
    );
  }
  if (file.status === 'analysis_failed') {
    return (
      <button
        onClick={onRetry}
        {...hoverProps}
        style={{
          fontSize: 12.5,
          fontWeight: 500,
          padding: '7px 14px',
          borderRadius: 999,
          border: '1px solid rgba(178,90,62,0.4)',
          background: isHovered ? 'rgba(178,90,62,0.1)' : 'transparent',
          color: '#E08A6C',
        }}
      >
        다시 시도
      </button>
    );
  }
  if (file.status === 'upload_failed') {
    return (
      <span style={{ fontSize: 12, padding: '5px 11px', borderRadius: 999, background: 'rgba(178,90,62,0.16)', color: '#E08A6C' }}>
        업로드실패
      </span>
    );
  }
  return null;
}

function DeleteButton({ onClick }: { onClick: () => void }) {
  const { isHovered, hoverProps } = useHover();
  return (
    <button
      onClick={onClick}
      {...hoverProps}
      aria-label="삭제"
      style={{
        width: 24,
        height: 24,
        borderRadius: '50%',
        border: 'none',
        background: isHovered ? 'rgba(var(--ink-rgb), 0.1)' : 'transparent',
        color: 'var(--text)',
        opacity: 0.6,
        fontSize: 13,
      }}
    >
      ×
    </button>
  );
}

function Spinner() {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 13,
        height: 13,
        borderRadius: '50%',
        border: '2px solid rgba(var(--ink-rgb), 0.2)',
        borderTopColor: 'var(--accent-text)',
        animation: 'spin 0.8s linear infinite',
      }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  );
}
