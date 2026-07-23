import { useAppState } from '../../state/AppState';
import type { TabId } from '../../state/AppState';
import { fonts } from '../../theme/tokens';
import { useHover } from '../../utils/useHover';
import { UploadTab } from './tabs/UploadTab';
import { WikiTab } from './tabs/WikiTab';
import { ChatTab } from './tabs/ChatTab';

const TABS: { id: TabId; label: (approvedCount: number) => string }[] = [
  { id: 'upload', label: () => '문서 등록' },
  { id: 'wiki', label: (count) => `위키 · ${count}` },
  { id: 'chat', label: () => '질문하기' },
];

export function SpaceMain() {
  const { spaces, activeSpaceId, activeTab, setActiveTab, resetAll } = useAppState();
  const activeSpace = spaces.find((s) => s.space_id === activeSpaceId);

  if (!activeSpace) return null;

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-text)' }} />
        <span style={{ fontFamily: fonts.mono, fontSize: 11.5, letterSpacing: 1, opacity: 0.6 }}>
          SPACE · {activeSpace.space_id}
        </span>
      </div>
      <h1 style={{ fontFamily: fonts.heading, fontWeight: 500, fontSize: 32, margin: '0 0 6px' }}>
        {activeSpace.name}
      </h1>
      {activeSpace.description && (
        <p style={{ margin: '0 0 22px', opacity: 0.65, fontSize: 14 }}>{activeSpace.description}</p>
      )}

      <div
        style={{
          display: 'flex',
          gap: 24,
          borderBottom: '1px solid rgba(var(--ink-rgb), 0.1)',
          marginBottom: 24,
        }}
      >
        {TABS.map((tab) => (
          <TabButton
            key={tab.id}
            label={tab.label(activeSpace.approved_count)}
            isActive={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          />
        ))}
      </div>

      <div style={{ flex: 1 }}>
        {activeTab === 'upload' && <UploadTab />}
        {activeTab === 'wiki' && <WikiTab />}
        {activeTab === 'chat' && <ChatTab approvedCount={activeSpace.approved_count} />}
      </div>

      <div style={{ textAlign: 'right', marginTop: 40 }}>
        <button
          onClick={() => {
            if (window.confirm('모든 Space와 데이터를 초기화할까요? (데모 편의 기능)')) {
              resetAll();
            }
          }}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 12.5,
            opacity: 0.45,
            textDecoration: 'underline',
          }}
        >
        s
        </button>
      </div>
    </main>
  );
}

function TabButton({ label, isActive, onClick }: { label: string; isActive: boolean; onClick: () => void }) {
  const { isHovered, hoverProps } = useHover();
  return (
    <button
      onClick={onClick}
      {...hoverProps}
      style={{
        background: 'none',
        border: 'none',
        padding: '10px 2px',
        fontSize: 14.5,
        fontWeight: isActive ? 600 : 500,
        color: isActive ? 'var(--accent-text)' : isHovered ? 'var(--text)' : 'rgba(var(--ink-rgb), 0.6)',
        borderBottom: isActive ? '2px solid var(--accent-text)' : '2px solid transparent',
        marginBottom: -1,
      }}
    >
      {label}
    </button>
  );
}
