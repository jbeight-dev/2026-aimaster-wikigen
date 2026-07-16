import type { CSSProperties } from 'react';
import type { DocumentSection } from '../../api/types';
import { fonts } from '../../theme/tokens';
import { MarkdownBody } from './MarkdownBody';

const editableFieldStyle: CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 10,
  border: '1px solid rgba(var(--ink-rgb), 0.16)',
  background: 'transparent',
  color: 'var(--text)',
  fontSize: 14,
  lineHeight: 1.65,
  fontFamily: 'inherit',
  resize: 'vertical',
};

interface SectionRendererProps {
  section: DocumentSection;
  isEditing?: boolean;
  onChange?: (section: DocumentSection) => void;
}

export function SectionRenderer({ section, isEditing = false, onChange }: SectionRendererProps) {
  return (
    <div style={{ marginBottom: 22 }}>
      <h3
        style={{
          fontSize: 14.5,
          fontWeight: 600,
          color: 'var(--accent-text)',
          margin: '0 0 10px',
        }}
      >
        {section.heading}
      </h3>

      {section.type === 'text' &&
        (isEditing ? (
          <textarea
            value={section.paragraphs.join('\n\n')}
            onChange={(e) =>
              onChange?.({ ...section, paragraphs: e.target.value.split(/\n\s*\n/).filter((p) => p.trim()) })
            }
            rows={Math.max(3, section.paragraphs.join('\n\n').split('\n').length)}
            style={editableFieldStyle}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {section.paragraphs.map((p, i) => (
              <p key={i} style={{ margin: 0, fontSize: 14, lineHeight: 1.65, opacity: 0.85 }}>
                {p}
              </p>
            ))}
          </div>
        ))}

      {section.type === 'markdown' &&
        (isEditing ? (
          <textarea
            value={section.content}
            onChange={(e) => onChange?.({ ...section, content: e.target.value })}
            rows={Math.max(8, section.content.split('\n').length)}
            style={{ ...editableFieldStyle, fontFamily: fonts.mono, fontSize: 12.5 }}
          />
        ) : (
          <MarkdownBody content={section.content} />
        ))}

      {section.type === 'tags' &&
        (isEditing ? (
          <input
            value={section.tags.join(', ')}
            onChange={(e) =>
              onChange?.({
                ...section,
                tags: e.target.value
                  .split(',')
                  .map((t) => t.trim())
                  .filter(Boolean),
              })
            }
            placeholder="태그를 쉼표(,)로 구분해 입력하세요"
            style={editableFieldStyle}
          />
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {section.tags.map((tag) => (
              <span
                key={tag}
                style={{
                  fontSize: 12.5,
                  padding: '5px 12px',
                  borderRadius: 999,
                  background: 'rgba(var(--ink-rgb), 0.06)',
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        ))}

      {section.type === 'table' && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {section.columns.map((col) => (
                  <th
                    key={col}
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
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {section.rows.map((row, i) => (
                <tr key={i}>
                  {section.columns.map((col) => (
                    <td
                      key={col}
                      style={{
                        padding: '8px 10px',
                        borderBottom: '1px solid rgba(var(--ink-rgb), 0.06)',
                      }}
                    >
                      {String(row[col] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
