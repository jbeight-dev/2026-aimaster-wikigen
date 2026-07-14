import { useTheme } from './theme/useTheme';
import { useAppState } from './state/AppState';
import { BackgroundDecor } from './components/layout/BackgroundDecor';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { EmptyState } from './components/onboarding/EmptyState';
import { SpaceMain } from './components/space/SpaceMain';
import { ReviewScreen } from './components/review/ReviewScreen';
import { CreateSpaceModal } from './components/modals/CreateSpaceModal';

function App() {
  const { theme, toggleTheme } = useTheme();
  const { isLoading, spaces, activeReviewDocId, isCreateSpaceModalOpen, hasVisitedLanding } = useAppState();

  const isEmptyStage = !isLoading && (spaces.length === 0 || !hasVisitedLanding);
  const isReviewStage = !isEmptyStage && activeReviewDocId !== null;
  const isListStage = !isLoading && !isEmptyStage && !isReviewStage;

  return (
    <div style={{ position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <BackgroundDecor />
      <Header theme={theme} toggleTheme={toggleTheme} />
      <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative', zIndex: 1 }}>
        {isLoading && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.5 }}>
            불러오는 중...
          </div>
        )}
        {isEmptyStage && <EmptyState />}
        {isReviewStage && <ReviewScreen />}
        {isListStage && (
          <>
            <Sidebar />
            <SpaceMain />
          </>
        )}
      </div>
      {isCreateSpaceModalOpen && <CreateSpaceModal />}
    </div>
  );
}

export default App;
