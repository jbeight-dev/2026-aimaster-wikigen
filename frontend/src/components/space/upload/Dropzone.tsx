import { useRef, useState } from 'react';
import { fonts } from '../../../theme/tokens';
import { useHover } from '../../../utils/useHover';

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void;
}

export function Dropzone({ onFilesSelected }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setDragOver] = useState(false);
  const { isHovered, hoverProps } = useHover();

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    onFilesSelected(Array.from(fileList));
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      style={{
        border: `1.5px dashed ${isDragOver ? 'var(--accent-text)' : 'rgba(var(--ink-rgb), 0.2)'}`,
        borderRadius: 16,
        padding: '40px 24px',
        textAlign: 'center',
        background: isDragOver ? 'rgba(255,138,61,0.05)' : 'rgba(var(--ink-rgb), 0.02)',
        marginBottom: 20,
      }}
    >
      <div style={{ fontSize: 28, marginBottom: 10, opacity: 0.6 }}>⬆</div>
      <p style={{ margin: '0 0 4px', fontSize: 14.5 }}>파일을 드래그하거나 클릭하여 업로드하세요</p>
      <p style={{ margin: '0 0 18px', fontSize: 12, fontFamily: fonts.mono, opacity: 0.5 }}>
        TXT · Markdown · CSV · SQLite(db/sqlite/sqlite3)
      </p>
      <button
        onClick={() => inputRef.current?.click()}
        {...hoverProps}
        style={{
          padding: '10px 20px',
          borderRadius: 999,
          border: '1px solid rgba(var(--ink-rgb), 0.18)',
          background: isHovered ? 'rgba(var(--ink-rgb), 0.06)' : 'transparent',
          color: 'var(--text)',
          fontSize: 13.5,
          fontWeight: 500,
        }}
      >
        파일 선택
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = '';
        }}
      />
    </div>
  );
}
