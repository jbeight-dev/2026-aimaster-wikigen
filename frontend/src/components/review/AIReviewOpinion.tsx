import type { ReactNode } from 'react';
import type { VerificationReport } from '../../api/types';
import { fonts, shadows, surface } from '../../theme/tokens';
import { useHover } from '../../utils/useHover';

const SCORE_LEGEND: { score: string; label: string }[] = [
  { score: '1.00', label: '문제 없음' },
  { score: '0.95', label: '사소한 이슈 존재' },
  { score: '0.80', label: '일부 검토 필요' },
  { score: '0.60', label: '중요한 누락 존재' },
  { score: '0.30', label: '재생성 권장' },
];

const VERDICT_STYLE: Record<VerificationReport['verdict'], { label: string; background: string; color: string }> = {
  pass: { label: '통과', background: 'rgba(255,138,61,0.14)', color: 'var(--accent-text)' },
  review: { label: '확인 필요', background: 'rgba(178,90,62,0.16)', color: '#E08A6C' },
  regenerate: { label: '재생성 필요', background: 'rgba(178,90,62,0.22)', color: '#E08A6C' },
};

const SEVERITY_LABEL: Record<'low' | 'med' | 'high', string> = {
  low: '낮음',
  med: '중간',
  high: '높음',
};

const RELATION_ACTION_LABEL: Record<'keep' | 'prune' | 'add', string> = {
  keep: '유지',
  prune: '제거',
  add: '추가',
};

export function AIReviewOpinion({
  report,
  isLoading,
  error,
}: {
  report: VerificationReport | null;
  isLoading: boolean;
  error: string | null;
}) {
  if (!isLoading && !error && !report) return null;

  return (
    <div
      style={{
        marginBottom: 20,
        padding: '14px 18px',
        borderRadius: 10,
        background: 'rgba(var(--ink-rgb), 0.05)',
        fontFamily: fonts.body,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>AI 검토 의견</p>
        <ScoreLegendHint />
      </div>

      {isLoading && (
        <p style={{ margin: 0, fontSize: 12.5, opacity: 0.6 }}>검토 의견을 불러오는 중이에요…</p>
      )}

      {!isLoading && error && (
        <p style={{ margin: 0, fontSize: 12.5, color: '#E08A6C' }}>{error}</p>
      )}

      {!isLoading && !error && report && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 11.5,
                padding: '3px 10px',
                borderRadius: 999,
                background: VERDICT_STYLE[report.verdict].background,
                color: VERDICT_STYLE[report.verdict].color,
              }}
            >
              {VERDICT_STYLE[report.verdict].label}
            </span>
            <span style={{ fontSize: 12, opacity: 0.6, fontFamily: fonts.mono }}>
              score {report.score.toFixed(2)}
            </span>
          </div>

          {report.faithfulness.length > 0 && (
            <ReportSection title="근거 검증">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {report.faithfulness.map((finding, i) => (
                  <li key={i} style={{ color: finding.grounded ? 'inherit' : '#E08A6C' }}>
                    [{SEVERITY_LABEL[finding.severity]}] {finding.claim}
                    {!finding.grounded && ' (근거 없음)'}
                  </li>
                ))}
              </ul>
            </ReportSection>
          )}

          {report.completeness.length > 0 && (
            <ReportSection title="누락된 내용">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
                {report.completeness.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </ReportSection>
          )}

          {report.value_changes.length > 0 && (
            <ReportSection title="값 불일치">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
                {report.value_changes.map((change, i) => (
                  <li key={i}>
                    {change.original_value} → {change.changed_value}
                  </li>
                ))}
              </ul>
            </ReportSection>
          )}

          {report.schema_issues.length > 0 && (
            <ReportSection title="스키마 이슈">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
                {report.schema_issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </ReportSection>
          )}

          {report.relations.length > 0 && (
            <ReportSection title="관계 제안">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
                {report.relations.map((rel, i) => (
                  <li key={i}>
                    [{RELATION_ACTION_LABEL[rel.action]}] {rel.type} → {rel.target}
                  </li>
                ))}
              </ul>
            </ReportSection>
          )}
        </div>
      )}
    </div>
  );
}

function ScoreLegendHint() {
  const { isHovered, hoverProps } = useHover();

  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <span
        {...hoverProps}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 15,
          height: 15,
          borderRadius: '50%',
          fontSize: 10.5,
          fontWeight: 700,
          background: 'rgba(var(--ink-rgb), 0.14)',
          color: 'var(--text)',
          opacity: 0.7,
          cursor: 'help',
        }}
      >
        !
      </span>

      {isHovered && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: 8,
            padding: '10px 12px',
            borderRadius: 8,
            background: surface.background,
            color: surface.text,
            boxShadow: shadows.userMenu,
            fontSize: 12,
            whiteSpace: 'nowrap',
            zIndex: 10,
          }}
        >
          {SCORE_LEGEND.map(({ score, label }) => (
            <div key={score} style={{ display: 'flex', gap: 10, padding: '2px 0' }}>
              <span style={{ fontFamily: fonts.mono, opacity: 0.7, minWidth: 34 }}>{score}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      )}
    </span>
  );
}

function ReportSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 600, opacity: 0.75 }}>{title}</p>
      {children}
    </div>
  );
}
