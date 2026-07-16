import type { DocumentStatus } from '../../api/types';
import { useHover } from '../../utils/useHover';

interface ReviewActionBarProps {
  status: DocumentStatus;
  position?: 'top' | 'bottom';
  canEdit: boolean;
  isEditing: boolean;
  isSaving: boolean;
  isRejecting: boolean;
  reason: string;
  onReasonChange: (reason: string) => void;
  onStartReject: () => void;
  onCancelReject: () => void;
  onApprove: () => void;
  onConfirmReject: () => void;
  onReopen: () => void;
  onClose: () => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
}

export function ReviewActionBar({
  status,
  position = 'bottom',
  canEdit,
  isEditing,
  isSaving,
  isRejecting,
  reason,
  onReasonChange,
  onStartReject,
  onCancelReject,
  onApprove,
  onConfirmReject,
  onReopen,
  onClose,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
}: ReviewActionBarProps) {
  const containerStyle =
    position === 'bottom'
      ? {
          position: 'sticky' as const,
          bottom: 0,
          marginTop: 32,
          padding: '16px 4px',
          borderTop: '1px solid rgba(var(--ink-rgb), 0.1)',
          background: 'color-mix(in srgb, var(--bg) 85%, transparent)',
          backdropFilter: 'blur(10px)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }
      : {
          marginBottom: 20,
          padding: '0 0 16px',
          borderBottom: '1px solid rgba(var(--ink-rgb), 0.1)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        };

  if (isEditing) {
    return (
      <div style={containerStyle}>
        <ActionButton variant="ghost" onClick={onCancelEdit}>
          취소
        </ActionButton>
        <ActionButton variant="primary" onClick={onSaveEdit}>
          {isSaving ? '저장 중…' : '수정 저장'}
        </ActionButton>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {status === 'pending' && !isRejecting && (
        <>
          {canEdit && (
            <ActionButton variant="ghost" onClick={onStartEdit}>
              수정
            </ActionButton>
          )}
          <ActionButton variant="ghost" onClick={onStartReject}>
            반려
          </ActionButton>
          <ActionButton variant="primary" onClick={onApprove}>
            승인
          </ActionButton>
        </>
      )}

      {status === 'pending' && isRejecting && (
        <div style={{ display: 'flex', gap: 10, width: '100%', alignItems: 'center' }}>
          <input
            autoFocus
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
            placeholder="반려 사유를 입력하세요 (미입력 시 '사유 미입력'으로 기록돼요)"
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid rgba(var(--ink-rgb), 0.16)',
              background: 'transparent',
              color: 'var(--text)',
              fontSize: 13,
            }}
          />
          <ActionButton variant="ghost" onClick={onCancelReject}>
            취소
          </ActionButton>
          <ActionButton variant="danger" onClick={onConfirmReject}>
            반려 확정
          </ActionButton>
        </div>
      )}

      {status === 'approved' && (
        <>
          <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--accent-text)' }}>✓ 승인 완료</span>
          <div style={{ marginLeft: 'auto' }}>
            <ActionButton variant="ghost" onClick={onClose}>
              목록으로
            </ActionButton>
          </div>
        </>
      )}

      {status === 'rejected' && (
        <>
          {canEdit && (
            <ActionButton variant="ghost" onClick={onStartEdit}>
              수정
            </ActionButton>
          )}
          <ActionButton variant="primary" onClick={onReopen}>
            다시 검토 대기로
          </ActionButton>
          <ActionButton variant="ghost" onClick={onClose}>
            목록으로
          </ActionButton>
        </>
      )}
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  variant,
}: {
  children: string;
  onClick: () => void;
  variant: 'primary' | 'ghost' | 'danger';
}) {
  const { isHovered, hoverProps } = useHover();
  const styles = {
    primary: { background: isHovered ? '#ff9a56' : '#FF8A3D', color: '#0B0E13', border: 'none' },
    ghost: {
      background: isHovered ? 'rgba(var(--ink-rgb), 0.06)' : 'transparent',
      color: 'var(--text)',
      border: '1px solid rgba(var(--ink-rgb), 0.16)',
    },
    danger: {
      background: isHovered ? 'rgba(178,90,62,0.22)' : 'rgba(178,90,62,0.14)',
      color: '#E08A6C',
      border: '1px solid rgba(178,90,62,0.4)',
    },
  }[variant];

  return (
    <button
      onClick={onClick}
      {...hoverProps}
      style={{
        padding: '10px 18px',
        borderRadius: 10,
        fontSize: 13.5,
        fontWeight: 600,
        ...styles,
      }}
    >
      {children}
    </button>
  );
}
