import type { DocumentStatus, FileStatus } from '../api/types';

export interface BadgeStyle {
  label: string;
  background: string;
  color: string;
}

export function documentStatusStyle(status: DocumentStatus): BadgeStyle {
  switch (status) {
    case 'approved':
      return {
        label: '승인됨',
        background: 'rgba(255,138,61,0.14)',
        color: 'var(--accent-text)',
      };
    case 'rejected':
      return {
        label: '반려됨',
        background: 'rgba(178,90,62,0.16)',
        color: '#E08A6C',
      };
    case 'pending':
    default:
      return {
        label: '검토 대기',
        background: 'rgba(var(--ink-rgb), 0.08)',
        color: 'rgba(var(--ink-rgb), 0.6)',
      };
  }
}

export function fileStatusLabel(status: FileStatus): string {
  switch (status) {
    case 'uploaded':
      return '대기 중';
    case 'analyzing':
      return '분석 중';
    case 'done':
      return '분석 완료';
    case 'analysis_failed':
      return '분석 실패';
    case 'upload_failed':
      return '업로드 실패';
  }
}
