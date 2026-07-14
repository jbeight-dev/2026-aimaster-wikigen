import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import * as authApi from '../api/auth';
import * as spacesApi from '../api/spaces';
import * as filesApi from '../api/files';
import * as documentsApi from '../api/documents';
import * as chatApi from '../api/chat';
import { ApiError, setToken } from '../api/client';
import type { ChatMessage, Space, User, UploadedFile, WikiDocument } from '../api/types';
import { useAnalysisPolling } from './useAnalysisPolling';

export type TabId = 'upload' | 'wiki' | 'chat';

interface SpaceData {
  files: UploadedFile[];
  documents: WikiDocument[];
  chatMessages: ChatMessage[];
}

function emptySpaceData(): SpaceData {
  return { files: [], documents: [], chatMessages: [] };
}

const LANDING_VISITED_KEY = 'wikigen.landingVisited';

function getInitialLandingVisited(): boolean {
  return localStorage.getItem(LANDING_VISITED_KEY) === 'true';
}

type ActionResult = { ok: true } | { ok: false; message: string };

interface AppStateValue {
  isLoading: boolean;
  currentUser: User | null;
  users: User[];
  switchUser: (userId: string) => Promise<void>;

  spaces: Space[];
  activeSpaceId: string | null;
  selectSpace: (spaceId: string) => void;

  hasVisitedLanding: boolean;
  viewExistingSpaces: () => void;

  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  isAccountMenuOpen: boolean;
  setAccountMenuOpen: (open: boolean) => void;

  isCreateSpaceModalOpen: boolean;
  createSpaceStep: 'form' | 'success';
  createdSpace: Space | null;
  openCreateSpaceModal: () => void;
  closeCreateSpaceModal: () => void;
  submitCreateSpace: (name: string, description: string) => Promise<ActionResult>;
  goToUploadAfterCreate: () => void;

  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;

  activeSpaceData: SpaceData;

  uploadFiles: (files: File[]) => Promise<void>;
  startAnalyze: (fileId: string) => Promise<void>;
  retryAnalyze: (fileId: string) => Promise<void>;
  deleteFile: (fileId: string) => Promise<void>;

  activeReviewDocId: string | null;
  activeReviewDocument: WikiDocument | null;
  reviewOrigin: TabId;
  openReview: (documentId: string, origin?: TabId) => void;
  closeReview: () => void;
  approveDocument: (documentId: string) => Promise<void>;
  rejectDocument: (documentId: string, reason: string) => Promise<void>;
  reopenDocument: (documentId: string) => Promise<void>;

  loadChatMessages: (spaceId: string) => Promise<void>;
  sendChatMessage: (text: string) => Promise<void>;
  isChatSending: boolean;

  resetAll: () => Promise<void>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);

  const [spaces, setSpaces] = useState<Space[]>([]);
  const [activeSpaceId, setActiveSpaceId] = useState<string | null>(null);
  const [spaceData, setSpaceData] = useState<Record<string, SpaceData>>({});

  const [hasVisitedLanding, setHasVisitedLanding] = useState<boolean>(getInitialLandingVisited);

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isAccountMenuOpen, setAccountMenuOpen] = useState(false);

  const [isCreateSpaceModalOpen, setCreateSpaceModalOpen] = useState(false);
  const [createSpaceStep, setCreateSpaceStep] = useState<'form' | 'success'>('form');
  const [createdSpace, setCreatedSpace] = useState<Space | null>(null);

  const [activeTab, setActiveTab] = useState<TabId>('upload');

  const [activeReviewDocId, setActiveReviewDocId] = useState<string | null>(null);
  const [reviewOrigin, setReviewOrigin] = useState<TabId>('upload');

  const [isChatSending, setChatSending] = useState(false);

  const updateSpaceData = useCallback(
    (spaceId: string, patch: Partial<SpaceData> | ((prev: SpaceData) => Partial<SpaceData>)) => {
      setSpaceData((prev) => {
        const current = prev[spaceId] ?? emptySpaceData();
        const patchObj = typeof patch === 'function' ? patch(current) : patch;
        return { ...prev, [spaceId]: { ...current, ...patchObj } };
      });
    },
    [],
  );

  const refreshSpaceCounts = useCallback(async (spaceId: string) => {
    const { space } = await spacesApi.getSpace(spaceId);
    setSpaces((prev) => prev.map((s) => (s.space_id === spaceId ? space : s)));
  }, []);

  // ---- bootstrap: session restore + initial data ----
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const { user } = await authApi.getMe();
        if (!cancelled) setCurrentUser(user);
      } catch {
        const { token, user } = await authApi.switchUser('usr_hong');
        setToken(token);
        if (!cancelled) setCurrentUser(user);
      }
      const [{ items: userItems }, { items: spaceItems }] = await Promise.all([
        authApi.listUsers(),
        spacesApi.listSpaces(),
      ]);
      if (cancelled) return;
      setUsers(userItems);
      setSpaces(spaceItems);
      setIsLoading(false);
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const switchUser = useCallback(async (userId: string) => {
    const { token, user } = await authApi.switchUser(userId);
    setToken(token);
    setCurrentUser(user);
    setAccountMenuOpen(false);
  }, []);

  const toggleSidebar = useCallback(() => setSidebarCollapsed((v) => !v), []);

  const loadSpaceContent = useCallback(
    async (spaceId: string) => {
      const [{ items: fileItems }, { items: docItems }] = await Promise.all([
        filesApi.listFiles(spaceId),
        documentsApi.listDocuments(spaceId),
      ]);
      updateSpaceData(spaceId, { files: fileItems, documents: docItems });
    },
    [updateSpaceData],
  );

  const selectSpace = useCallback(
    (spaceId: string) => {
      setActiveSpaceId(spaceId);
      setActiveTab('upload');
      setActiveReviewDocId(null);
      setAccountMenuOpen(false);
      loadSpaceContent(spaceId);
    },
    [loadSpaceContent],
  );

  const openCreateSpaceModal = useCallback(() => {
    setCreateSpaceStep('form');
    setCreatedSpace(null);
    setCreateSpaceModalOpen(true);
  }, []);

  const closeCreateSpaceModal = useCallback(() => setCreateSpaceModalOpen(false), []);

  const submitCreateSpace = useCallback(
    async (name: string, description: string): Promise<ActionResult> => {
      if (!name.trim()) {
        return { ok: false, message: 'Space 이름을 입력해주세요.' };
      }
      try {
        const { space } = await spacesApi.createSpace(name.trim(), description.trim());
        setSpaces((prev) => [space, ...prev]);
        setCreatedSpace(space);
        setCreateSpaceStep('success');
        return { ok: true };
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Space 생성에 실패했어요.';
        return { ok: false, message };
      }
    },
    [],
  );

  const viewExistingSpaces = useCallback(() => {
    localStorage.setItem(LANDING_VISITED_KEY, 'true');
    setHasVisitedLanding(true);
  }, []);

  const goToUploadAfterCreate = useCallback(() => {
    if (!createdSpace) return;
    localStorage.setItem(LANDING_VISITED_KEY, 'true');
    setHasVisitedLanding(true);
    setCreateSpaceModalOpen(false);
    selectSpace(createdSpace.space_id);
  }, [createdSpace, selectSpace]);

  const uploadFiles = useCallback(
    async (fileList: File[]) => {
      if (!activeSpaceId) return;
      const { items } = await filesApi.uploadFiles(activeSpaceId, fileList);
      updateSpaceData(activeSpaceId, (prev) => ({ files: [...items, ...prev.files] }));
      await refreshSpaceCounts(activeSpaceId);
    },
    [activeSpaceId, updateSpaceData, refreshSpaceCounts],
  );

  const startAnalyze = useCallback(
    async (fileId: string) => {
      if (!activeSpaceId) return;
      updateSpaceData(activeSpaceId, (prev) => ({
        files: prev.files.map((f) =>
          f.file_id === fileId ? { ...f, status: 'analyzing' as UploadedFile['status'], step_index: 0 } : f,
        ),
      }));
      const { status } = await filesApi.analyzeFile(fileId);
      updateSpaceData(activeSpaceId, (prev) => ({
        files: prev.files.map((f) =>
          f.file_id === fileId ? { ...f, status: status as UploadedFile['status'], step_index: 0 } : f,
        ),
      }));
    },
    [activeSpaceId, updateSpaceData],
  );

  const retryAnalyze = useCallback(
    async (fileId: string) => {
      if (!activeSpaceId) return;
      updateSpaceData(activeSpaceId, (prev) => ({
        files: prev.files.map((f) =>
          f.file_id === fileId ? { ...f, status: 'analyzing' as UploadedFile['status'], step_index: 0 } : f,
        ),
      }));
      const { status } = await filesApi.retryFile(fileId);
      updateSpaceData(activeSpaceId, (prev) => ({
        files: prev.files.map((f) =>
          f.file_id === fileId ? { ...f, status: status as UploadedFile['status'], step_index: 0 } : f,
        ),
      }));
    },
    [activeSpaceId, updateSpaceData],
  );

  const deleteFile = useCallback(
    async (fileId: string) => {
      if (!activeSpaceId) return;
      await filesApi.deleteFile(fileId);
      updateSpaceData(activeSpaceId, (prev) => ({
        files: prev.files.filter((f) => f.file_id !== fileId),
        documents: prev.documents.filter((d) => d.file_id !== fileId),
      }));
      await refreshSpaceCounts(activeSpaceId);
    },
    [activeSpaceId, updateSpaceData, refreshSpaceCounts],
  );

  const openReview = useCallback((documentId: string, origin?: TabId) => {
    if (origin) setReviewOrigin(origin);
    setActiveReviewDocId(documentId);
  }, []);

  const closeReview = useCallback(() => setActiveReviewDocId(null), []);

  const approveDocument = useCallback(
    async (documentId: string) => {
      if (!activeSpaceId) return;
      const { document } = await documentsApi.approveDocument(documentId);
      updateSpaceData(activeSpaceId, (prev) => ({
        documents: prev.documents.map((d) => (d.document_id === documentId ? document : d)),
      }));
      await refreshSpaceCounts(activeSpaceId);
    },
    [activeSpaceId, updateSpaceData, refreshSpaceCounts],
  );

  const rejectDocument = useCallback(
    async (documentId: string, reason: string) => {
      if (!activeSpaceId) return;
      const { document } = await documentsApi.rejectDocument(documentId, reason);
      updateSpaceData(activeSpaceId, (prev) => ({
        documents: prev.documents.map((d) => (d.document_id === documentId ? document : d)),
      }));
    },
    [activeSpaceId, updateSpaceData],
  );

  const reopenDocument = useCallback(
    async (documentId: string) => {
      if (!activeSpaceId) return;
      const { document } = await documentsApi.reopenDocument(documentId);
      updateSpaceData(activeSpaceId, (prev) => ({
        documents: prev.documents.map((d) => (d.document_id === documentId ? document : d)),
      }));
      await refreshSpaceCounts(activeSpaceId);
    },
    [activeSpaceId, updateSpaceData, refreshSpaceCounts],
  );

  const loadChatMessages = useCallback(
    async (spaceId: string) => {
      const { items } = await chatApi.listMessages(spaceId);
      updateSpaceData(spaceId, { chatMessages: items });
    },
    [updateSpaceData],
  );

  const sendChatMessage = useCallback(
    async (text: string) => {
      if (!activeSpaceId || !text.trim()) return;
      setChatSending(true);
      try {
        const { user_message, assistant_message } = await chatApi.sendMessage(activeSpaceId, text.trim());
        updateSpaceData(activeSpaceId, (prev) => ({
          chatMessages: [...prev.chatMessages, user_message, assistant_message],
        }));
      } finally {
        setChatSending(false);
      }
    },
    [activeSpaceId, updateSpaceData],
  );

  const resetAll = useCallback(async () => {
    await spacesApi.deleteAllSpaces();
    setSpaces([]);
    setSpaceData({});
    setActiveSpaceId(null);
    setActiveTab('upload');
    setActiveReviewDocId(null);
    setAccountMenuOpen(false);
  }, []);

  const activeSpaceData = activeSpaceId ? spaceData[activeSpaceId] ?? emptySpaceData() : emptySpaceData();

  useAnalysisPolling(
    activeSpaceId,
    activeSpaceData.files,
    (updatedFiles) => {
      if (!activeSpaceId) return;
      updateSpaceData(activeSpaceId, (prev) => ({
        files: prev.files.map((f) => updatedFiles.find((u) => u.file_id === f.file_id) ?? f),
      }));
    },
    (documents) => {
      if (!activeSpaceId) return;
      updateSpaceData(activeSpaceId, { documents });
      refreshSpaceCounts(activeSpaceId);
    },
  );

  const activeReviewDocument = activeReviewDocId
    ? activeSpaceData.documents.find((d) => d.document_id === activeReviewDocId) ?? null
    : null;

  const value = useMemo<AppStateValue>(
    () => ({
      isLoading,
      currentUser,
      users,
      switchUser,
      spaces,
      activeSpaceId,
      selectSpace,
      hasVisitedLanding,
      viewExistingSpaces,
      sidebarCollapsed,
      toggleSidebar,
      isAccountMenuOpen,
      setAccountMenuOpen,
      isCreateSpaceModalOpen,
      createSpaceStep,
      createdSpace,
      openCreateSpaceModal,
      closeCreateSpaceModal,
      submitCreateSpace,
      goToUploadAfterCreate,
      activeTab,
      setActiveTab,
      activeSpaceData,
      uploadFiles,
      startAnalyze,
      retryAnalyze,
      deleteFile,
      activeReviewDocId,
      activeReviewDocument,
      reviewOrigin,
      openReview,
      closeReview,
      approveDocument,
      rejectDocument,
      reopenDocument,
      loadChatMessages,
      sendChatMessage,
      isChatSending,
      resetAll,
    }),
    [
      isLoading,
      currentUser,
      users,
      switchUser,
      spaces,
      activeSpaceId,
      selectSpace,
      hasVisitedLanding,
      viewExistingSpaces,
      sidebarCollapsed,
      toggleSidebar,
      isAccountMenuOpen,
      isCreateSpaceModalOpen,
      createSpaceStep,
      createdSpace,
      openCreateSpaceModal,
      closeCreateSpaceModal,
      submitCreateSpace,
      goToUploadAfterCreate,
      activeTab,
      activeSpaceData,
      uploadFiles,
      startAnalyze,
      retryAnalyze,
      deleteFile,
      activeReviewDocId,
      activeReviewDocument,
      reviewOrigin,
      openReview,
      closeReview,
      approveDocument,
      rejectDocument,
      reopenDocument,
      loadChatMessages,
      sendChatMessage,
      isChatSending,
      resetAll,
    ],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error('useAppState must be used within AppStateProvider');
  return ctx;
}
