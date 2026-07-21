"use client";

import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { createPortal } from "react-dom";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Download,
  FileJson,
  KeyRound,
  Loader2,
  MessageCirclePlus,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Send,
  Settings,
  Sparkles,
  Trash2,
  X
} from "lucide-react";
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import { IMAGENT_GENERATION_MODEL_ID, IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  imageUrl?: string;
  imageFileName?: string;
  traceUrl?: string;
  provider?: string;
  agentId?: string;
  capability?: string;
  candidateCount?: number;
  roundCount?: number;
  selectedCandidateIndex?: number;
  model?: string;
  quality?: string;
  costUsd?: number;
  latencyMs?: number;
  error?: string;
};

type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
};

type ModalState =
  | { type: "settings" }
  | { type: "edit"; sessionId: string }
  | { type: "delete"; sessionId: string }
  | { type: "delete-all"; returnToSettings?: boolean }
  | null;

type ApiKeyVerificationStatus = "idle" | "verifying" | "valid" | "invalid";

type ApiKeyVerification = {
  status: ApiKeyVerificationStatus;
  message: string;
};

type VerifyResponse = {
  verified?: boolean;
  key?: {
    label?: string;
    limit_remaining?: number | null;
  } | null;
  warning?: string;
  usingServerKey?: boolean;
  error?: string;
};

type RuntimeStatusResponse = {
  ready: boolean;
  hasServerApiKey: boolean;
  issues: string[];
};

type GenerateResponse = {
  runId?: string;
  imageUrl?: string;
  imageFileName?: string;
  provider?: string;
  agentId?: string;
  capability?: string;
  candidateCount?: number;
  roundCount?: number;
  selectedCandidateIndex?: number;
  traceUrl?: string;
  model?: string;
  costUsd?: number;
  latencyMs?: number;
  error?: string;
};

const SESSIONS_KEY = "imagent.chatSessions";
const ACTIVE_SESSION_KEY = "imagent.activeSession";
const SETTINGS_KEY = "imagent.generationSettings";
const levelOptions = ["auto", "low", "medium", "high"];

const templatePrompts = [
  "Cinematic AI image-agent command room with glowing canvases, cyan glass panels, premium launch poster.",
  "Golden benchmark winner poster with crown signal, agent leaderboard energy, dramatic studio lighting.",
  "Futuristic Gittensor creator network with luminous miner nodes, flowing image thumbnails, deep teal atmosphere.",
  "Elegant Imagent whitepaper cover showing plan, generate, critique, iterate as connected visual stages."
];

const modalFocusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

const emptySession: ChatSession = {
  id: "new-session",
  title: "New Session",
  createdAt: "",
  updatedAt: "",
  messages: []
};

export function GenerationChat() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [level, setLevel] = useState("auto");
  const [apiKey, setApiKey] = useState("");
  const [draftApiKey, setDraftApiKey] = useState("");
  const [apiKeyVerification, setApiKeyVerification] = useState<ApiKeyVerification>({
    status: "idle",
    message: "Enter key"
  });
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusResponse | null>(null);
  const [runtimeError, setRuntimeError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatingSessionId, setGeneratingSessionId] = useState("");
  const [modal, setModal] = useState<ModalState>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [levelMenuOpen, setLevelMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const modalRef = useRef<HTMLElement | null>(null);
  const modalTriggerRef = useRef<HTMLElement | null>(null);
  const closeModalRef = useRef<() => void>(() => {});
  const preserveModalTriggerRef = useRef(false);
  const promptTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  async function loadRuntimeStatus() {
    try {
      const response = await fetch("/api/playground/status", { cache: "no-store" });
      const data = (await response.json()) as RuntimeStatusResponse;
      setRuntimeStatus(data);
      setRuntimeError("");
    } catch (error) {
      setRuntimeStatus(null);
      setRuntimeError(error instanceof Error ? error.message : "Failed to check the Imagent runtime.");
    }
  }

  useEffect(() => {
    setMounted(true);
    const savedSessions = sanitizeSessions(readJson<ChatSession[]>(SESSIONS_KEY, []));
    const savedSettings = readJson<{ level?: string }>(SETTINGS_KEY, {});
    const initialSessions = savedSessions.length ? savedSessions : [newSession()];
    const savedActive = localStorage.getItem(ACTIVE_SESSION_KEY);
    const activeId = savedActive && initialSessions.some((session) => session.id === savedActive)
      ? savedActive
      : initialSessions[0].id;
    const initialLevel = isLevelOption(savedSettings.level) ? savedSettings.level : "auto";

    setSessions(initialSessions);
    setActiveSessionId(activeId);
    setLevel(initialLevel);
    void loadRuntimeStatus();
  }, []);

  useEffect(() => {
    if (sessions.length) {
      localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    }
  }, [sessions]);

  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
    }
  }, [activeSessionId]);

  useEffect(() => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({ level }));
  }, [level]);

  useEffect(() => {
    closeModalRef.current = closeModal;
  });

  useLayoutEffect(() => {
    const textarea = promptTextareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";
    const maxHeight = 144;
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [prompt]);

  useEffect(() => {
    if (!modal) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    const fallbackTrigger = modalTriggerRef.current;
    const focusTimer = window.setTimeout(() => {
      const focusTarget = firstFocusableElement(modalRef.current) || modalRef.current;
      focusTarget?.focus({ preventScroll: true });
    }, 0);
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeModalRef.current();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const dialog = modalRef.current;
      if (!dialog) {
        return;
      }

      const focusableElements = getFocusableElements(dialog);
      if (!focusableElements.length) {
        event.preventDefault();
        dialog.focus({ preventScroll: true });
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;

      if (event.shiftKey) {
        if (!dialog.contains(activeElement) || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus({ preventScroll: true });
        }
        return;
      }

      if (!dialog.contains(activeElement) || activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus({ preventScroll: true });
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      if (preserveModalTriggerRef.current) {
        preserveModalTriggerRef.current = false;
        return;
      }

      const trigger = modalTriggerRef.current?.isConnected ? modalTriggerRef.current : fallbackTrigger;
      if (trigger?.isConnected) {
        trigger.focus({ preventScroll: true });
      }
      modalTriggerRef.current = null;
    };
  }, [modal]);

  useEffect(() => {
    if (modal?.type !== "settings") {
      return;
    }

    const key = draftApiKey.trim();
    if (!key && runtimeStatus === null && !runtimeError) {
      setApiKeyVerification({ status: "verifying", message: "Checking runtime" });
      return;
    }

    if (!key && !runtimeStatus?.hasServerApiKey) {
      setApiKeyVerification({ status: "idle", message: "Enter key" });
      return;
    }

    const controller = new AbortController();
    setApiKeyVerification({ status: "verifying", message: "Checking" });

    const verifyTimer = window.setTimeout(async () => {
      try {
        const response = await fetch("/api/openrouter/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(key ? { apiKey: key } : {}),
          signal: controller.signal
        });
        const data = (await response.json()) as VerifyResponse;

        if (!response.ok || data.error || !data.verified) {
          throw new Error(data.error || `Verification failed with HTTP ${response.status}`);
        }

        setApiKeyVerification({
          status: "valid",
          message: data.warning || (data.usingServerKey ? "Server key" : data.key?.label || "Verified")
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setApiKeyVerification({
          status: "invalid",
          message: error instanceof Error ? error.message : "Invalid key"
        });
      }
    }, 650);

    return () => {
      controller.abort();
      window.clearTimeout(verifyTimer);
    };
  }, [draftApiKey, modal, runtimeError, runtimeStatus]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) || sessions[0] || emptySession,
    [activeSessionId, sessions]
  );
  const visibleSessions = sessions.length ? sessions : [emptySession];
  const hasMessages = Boolean(activeSession?.messages.length);
  const hasServerApiKey = Boolean(runtimeStatus?.hasServerApiKey);
  const hasConfiguredOpenRouter = hasServerApiKey || apiKey.trim().length > 0;
  const activeIsGenerating = isGenerating && generatingSessionId === activeSession.id;
  const canSend = prompt.trim().length > 0 && !isGenerating;
  const canSaveSettings = !draftApiKey.trim() || apiKeyVerification.status === "valid";
  const canDeleteAllSessions = sessions.length > 1 || sessions.some((session) => session.messages.length > 0);
  const modalSession = modal && "sessionId" in modal
    ? sessions.find((session) => session.id === modal.sessionId)
    : null;

  function createSession() {
    const reusableSession = sessions.find((session) => session.messages.length === 0);
    if (reusableSession) {
      setActiveSessionId(reusableSession.id);
      setPrompt("");
      setSidebarCollapsed(false);
      return;
    }

    const session = newSession();
    setSessions((current) => [session, ...current]);
    setActiveSessionId(session.id);
    setPrompt("");
    setSidebarCollapsed(false);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendPrompt(prompt);
  }

  function handlePromptKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    if (canSend) {
      void sendPrompt(prompt);
    }
  }

  function selectTemplate(template: string) {
    void sendPrompt(template);
  }

  async function sendPrompt(value: string) {
    const content = value.trim();
    if (!content || isGenerating) {
      return;
    }

    const now = new Date().toISOString();
    const sessionId = sessions.length ? activeSession.id : crypto.randomUUID();
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      createdAt: now
    };

    if (!hasConfiguredOpenRouter) {
      openSettings();
      return;
    }

    appendSessionMessages(sessionId, [userMessage], titleFromPrompt(content), now);
    setPrompt("");

    if (runtimeStatus && !runtimeStatus.ready) {
      appendSessionMessages(sessionId, [
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Imagent runtime is not ready",
          createdAt: new Date().toISOString(),
          error: runtimeStatus.issues.join(" ") || runtimeError || "Runtime is not ready.",
          model: IMAGENT_GENERATION_MODEL_ID,
          quality: level
        }
      ]);
      void loadRuntimeStatus();
      return;
    }

    setIsGenerating(true);
    setGeneratingSessionId(sessionId);

    try {
      const response = await fetch("/api/playground/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: content,
          apiKey: apiKey.trim() || undefined,
          quality: level
        })
      });
      const data = (await response.json()) as GenerateResponse;
      if (!response.ok || data.error) {
        throw new Error(data.error || `Generation failed with HTTP ${response.status}`);
      }

      appendSessionMessages(sessionId, [
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Generated with Imagent",
          createdAt: new Date().toISOString(),
          imageUrl: data.imageUrl,
          imageFileName: data.imageFileName,
          traceUrl: data.traceUrl,
          provider: data.provider,
          agentId: data.agentId,
          capability: data.capability,
          candidateCount: data.candidateCount,
          roundCount: data.roundCount,
          selectedCandidateIndex: data.selectedCandidateIndex,
          model: data.model || IMAGENT_GENERATION_MODEL_ID,
          quality: level,
          costUsd: data.costUsd,
          latencyMs: data.latencyMs
        }
      ]);
    } catch (error) {
      appendSessionMessages(sessionId, [
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Imagent generation failed",
          createdAt: new Date().toISOString(),
          error: error instanceof Error ? error.message : "Unknown generation error",
          model: IMAGENT_GENERATION_MODEL_ID,
          quality: level
        }
      ]);
      void loadRuntimeStatus();
    } finally {
      setIsGenerating(false);
      setGeneratingSessionId("");
    }
  }

  function appendSessionMessages(sessionId: string, appendedMessages: ChatMessage[], nextTitle?: string, createdAt?: string) {
    setSessions((current) => {
      const now = new Date().toISOString();
      if (!current.some((session) => session.id === sessionId)) {
        return [
          {
            id: sessionId,
            title: nextTitle || "New Session",
            createdAt: createdAt || now,
            updatedAt: now,
            messages: appendedMessages
          },
          ...current
        ];
      }

      return current.map((session) => {
        if (session.id !== sessionId) {
          return session;
        }
        return {
          ...session,
          title: session.title === "New Session" && nextTitle ? nextTitle : session.title,
          updatedAt: now,
          messages: [...session.messages, ...appendedMessages]
        };
      });
    });
    setActiveSessionId(sessionId);
  }

  function openSettings() {
    setModalTrigger();
    setLevelMenuOpen(false);
    setDraftApiKey(apiKey);
    setModal({ type: "settings" });
    void loadRuntimeStatus();
  }

  function updateLevel(value: string) {
    if (!isLevelOption(value)) {
      return;
    }
    setLevel(value);
    setLevelMenuOpen(false);
  }

  function openEditSession(session: ChatSession, event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    setModalTrigger(event.currentTarget);
    setLevelMenuOpen(false);
    setDraftTitle(session.title);
    setModal({ type: "edit", sessionId: session.id });
  }

  function openDeleteSession(session: ChatSession, event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    setModalTrigger(event.currentTarget);
    setLevelMenuOpen(false);
    setModal({ type: "delete", sessionId: session.id });
  }

  function openDeleteAllSessions() {
    if (!canDeleteAllSessions) {
      return;
    }

    preserveModalTriggerRef.current = true;
    setModal({ type: "delete-all", returnToSettings: true });
  }

  function closeModal() {
    if (modal?.type === "delete-all" && modal.returnToSettings) {
      preserveModalTriggerRef.current = true;
      setModal({ type: "settings" });
      void loadRuntimeStatus();
      return;
    }

    setModal(null);
    setDraftTitle("");
  }

  function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSaveSettings) {
      return;
    }
    setApiKey(draftApiKey.trim());
    closeModal();
  }

  function setModalTrigger(fallback?: HTMLElement | null) {
    const activeElement = document.activeElement;
    modalTriggerRef.current = activeElement instanceof HTMLElement && activeElement !== document.body
      ? activeElement
      : fallback || null;
  }

  function saveSessionTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!modal || modal.type !== "edit") {
      return;
    }

    const nextTitle = draftTitle.replace(/\s+/g, " ").trim() || "New Session";
    setSessions((current) =>
      current.map((session) =>
        session.id === modal.sessionId
          ? { ...session, title: titleFromPrompt(nextTitle), updatedAt: new Date().toISOString() }
          : session
      )
    );
    closeModal();
  }

  function deleteSession() {
    if (!modal || modal.type !== "delete") {
      return;
    }

    const remainingSessions = sessions.filter((session) => session.id !== modal.sessionId);
    if (!remainingSessions.length) {
      const replacement = newSession();
      setSessions([replacement]);
      setActiveSessionId(replacement.id);
      closeModal();
      return;
    }

    setSessions(remainingSessions);
    if (!remainingSessions.some((session) => session.id === activeSessionId)) {
      setActiveSessionId(remainingSessions[0].id);
    }
    closeModal();
  }

  function deleteAllSessions() {
    const shouldReturnToSettings = modal?.type === "delete-all" && modal.returnToSettings;
    const replacement = newSession();
    setSessions([replacement]);
    setActiveSessionId(replacement.id);
    setPrompt("");
    if (shouldReturnToSettings) {
      preserveModalTriggerRef.current = true;
      setModal({ type: "settings" });
      void loadRuntimeStatus();
      return;
    }

    closeModal();
  }

  function handleBackdropMouseDown(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) {
      closeModal();
    }
  }

  return (
    <div className="imagent-landing generation-shell generation-redesign">
      <LandingBackgroundFx />
      <ScrollReveal />

      <main
        className={sidebarCollapsed ? "generation-chat-layout session-collapsed" : "generation-chat-layout"}
        aria-label="Generation session workspace"
      >
        <div className="generation-workspace-surface">
          <aside className={sidebarCollapsed ? "generation-session-panel collapsed" : "generation-session-panel"} aria-label="Session history">
            <div className="generation-session-header">
              <button
                className="generation-icon-button"
                type="button"
                aria-label={sidebarCollapsed ? "Expand sessions" : "Collapse sessions"}
                title={sidebarCollapsed ? "Expand sessions" : "Collapse sessions"}
                onClick={() => setSidebarCollapsed((current) => !current)}
              >
                {sidebarCollapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
              </button>
              {sidebarCollapsed ? null : <span>Sessions</span>}
              <button
                className="generation-icon-button primary"
                type="button"
                aria-label="New session"
                title="New session"
                onClick={createSession}
              >
                <MessageCirclePlus size={21} />
              </button>
            </div>

            {sidebarCollapsed ? (
              <div className="generation-session-rail custom-scrollbar">
                {visibleSessions.map((session) => (
                  <button
                    className={session.id === activeSession?.id ? "generation-rail-session active" : "generation-rail-session"}
                    type="button"
                    key={session.id}
                    aria-label={session.title}
                    title={session.title}
                    onClick={() => {
                      if (sessions.length) {
                        setActiveSessionId(session.id);
                      }
                    }}
                  >
                    <MessageSquareText size={16} />
                  </button>
                ))}
              </div>
            ) : (
              <div className="generation-session-list custom-scrollbar">
                {visibleSessions.map((session) => {
                  const active = session.id === activeSession?.id;
                  return (
                    <div className={active ? "generation-session-item active" : "generation-session-item"} key={session.id}>
                      <button
                        className="generation-session-select"
                        type="button"
                        onClick={() => {
                          if (sessions.length) {
                            setActiveSessionId(session.id);
                          }
                        }}
                      >
                        <MessageSquareText size={16} />
                        <span>{session.title}</span>
                      </button>
                      {sessions.length ? (
                        <div className="generation-session-actions" aria-label={`${session.title} actions`}>
                          <button type="button" aria-label="Edit session title" title="Edit" onClick={(event) => openEditSession(session, event)}>
                            <Pencil size={14} />
                          </button>
                          <button type="button" aria-label="Delete session" title="Delete" onClick={(event) => openDeleteSession(session, event)}>
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}

            <div className="generation-session-footer">
              <button
                className="generation-sidebar-settings"
                type="button"
                aria-label="Open generation settings"
                title="Settings"
                onClick={openSettings}
              >
                <Settings size={17} />
                {sidebarCollapsed ? null : <span>Settings</span>}
              </button>
            </div>
          </aside>

          <section className="generation-chat-panel" aria-label="Chat">
            <header className="generation-chat-head">
              <div className="generation-model-row">
                <span className="generation-model-pill">
                  <Sparkles size={15} />
                  <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong>
                </span>
              </div>
              <div
                className={levelMenuOpen ? "generation-level-menu open" : "generation-level-menu"}
                onBlur={(event) => {
                  const nextFocus = event.relatedTarget as Node | null;
                  if (!event.currentTarget.contains(nextFocus)) {
                    setLevelMenuOpen(false);
                  }
                }}
              >
                <button
                  className="generation-level-trigger"
                  type="button"
                  aria-haspopup="listbox"
                  aria-expanded={levelMenuOpen}
                  onClick={() => setLevelMenuOpen((current) => !current)}
                >
                  <span>{level}</span>
                  <ChevronDown size={14} aria-hidden="true" />
                </button>
                {levelMenuOpen ? (
                  <div className="generation-level-menu-list" role="listbox" aria-label="Generation level">
                    {levelOptions.map((option) => (
                      <button
                        className={level === option ? "active" : ""}
                        type="button"
                        role="option"
                        aria-selected={level === option}
                        key={option}
                        onClick={() => updateLevel(option)}
                      >
                        <span>{option}</span>
                        {level === option ? <Check size={13} /> : null}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </header>

            <div className="generation-chat-history custom-scrollbar">
              {hasMessages ? (
                <>
                  {activeSession.messages.map((message) => {
                    const metaItems = messageMetaItems(message);
                    return (
                      <article
                        className={`generation-message ${message.role}${message.error ? " error" : ""}${message.imageUrl ? " with-image" : ""}`}
                        key={message.id}
                      >
                        <span>{message.role === "user" ? "You" : "Imagent"}</span>
                        <p>{message.error || message.content}</p>
                        {message.imageUrl ? (
                          <>
                            <div className="generation-message-image">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={message.imageUrl} alt="Generated image" />
                            </div>
                            <div className="generation-message-actions">
                              <a href={message.imageUrl} download={message.imageFileName || "imagent-output.png"}>
                                <Download size={15} />
                                Download Image
                              </a>
                              {message.traceUrl ? (
                                <a href={message.traceUrl} target="_blank" rel="noreferrer">
                                  <FileJson size={15} />
                                  View Trace
                                </a>
                              ) : null}
                            </div>
                          </>
                        ) : null}
                        {metaItems.length ? (
                          <div className="generation-message-meta">
                            {metaItems.map((item) => (
                              <span key={item}>{item}</span>
                            ))}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                  {activeIsGenerating ? (
                    <article className="generation-message assistant generation-message-loading" aria-live="polite">
                      <span>Imagent</span>
                      <p>
                        <Loader2 className="spin" size={15} />
                        Agent is generating with OpenRouter...
                      </p>
                    </article>
                  ) : null}
                </>
              ) : (
                <div className="generation-empty-state">
                  <h1>What&apos;s your agenda today?</h1>
                  <div className="generation-template-grid">
                    {templatePrompts.map((template) => (
                      <button type="button" key={template} onClick={() => selectTemplate(template)}>
                        {template}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <form className="generation-chat-input" onSubmit={submit}>
              <div className="generation-input-control">
                <div className="generation-input-row">
                  <textarea
                    className="custom-scrollbar"
                    ref={promptTextareaRef}
                    value={prompt}
                    onChange={(event) => setPrompt(event.target.value)}
                    onKeyDown={handlePromptKeyDown}
                    placeholder="Type your agenda..."
                    rows={1}
                    aria-label="Generation prompt"
                  />
                  <button
                    className="generation-input-icon-button generation-send-button"
                    type="submit"
                    disabled={!canSend}
                    aria-label="Send agenda"
                  >
                    {isGenerating ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                  </button>
                </div>
              </div>
            </form>
          </section>
        </div>
      </main>

      {mounted && modal
        ? createPortal(
            <div className="generation-modal-backdrop" role="presentation" onMouseDown={handleBackdropMouseDown}>
              <div className={`generation-dialog-card${modal.type === "settings" ? " generation-settings-card" : ""}`}>
                {modal.type === "settings" ? (
                  <form
                    className="generation-dialog generation-settings-dialog"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="generation-settings-title"
                    onSubmit={saveSettings}
                    ref={(node) => {
                      modalRef.current = node;
                    }}
                    tabIndex={-1}
                  >
                    <header>
                      <span className="generation-dialog-icon generation-settings-icon" aria-hidden="true">
                        <Settings size={30} />
                      </span>
                      <h2 id="generation-settings-title">Settings</h2>
                      <button className="generation-dialog-close generation-settings-close" type="button" aria-label="Close settings" onClick={closeModal}>
                        <X size={20} />
                      </button>
                    </header>
                    <div className="generation-dialog-body">
                      <label className="generation-setting-row generation-api-key-field">
                        <span>OpenRouter API key</span>
                        <div className={`generation-api-key-control ${apiKeyVerification.status}`}>
                          <input
                            autoComplete="off"
                            onChange={(event) => setDraftApiKey(event.target.value)}
                            placeholder="sk-or-v1-..."
                            spellCheck={false}
                            type="password"
                            value={draftApiKey}
                          />
                          <span className={`generation-api-key-status ${apiKeyVerification.status}`} aria-live="polite">
                            {apiKeyVerification.status === "verifying" ? <Loader2 className="spin" size={14} /> : null}
                            {apiKeyVerification.status === "valid" ? <Check size={14} /> : null}
                            {apiKeyVerification.status === "invalid" ? <AlertTriangle size={14} /> : null}
                            {apiKeyVerification.status === "idle" ? <KeyRound size={14} /> : null}
                            <span>{apiKeyVerification.message}</span>
                          </span>
                        </div>
                      </label>
                      <div className="generation-setting-row generation-model-setting">
                        <span>Model</span>
                        <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong>
                      </div>
                      <div className="generation-setting-row generation-delete-all-setting">
                        <div className="generation-setting-action-copy">
                          <strong>Local History</strong>
                          <small>Clear every session saved in this browser.</small>
                        </div>
                        <button
                          className="generation-settings-danger-action"
                          type="button"
                          disabled={!canDeleteAllSessions}
                          onClick={openDeleteAllSessions}
                        >
                          <Trash2 size={15} />
                          Delete All
                        </button>
                      </div>
                    </div>
                    <footer>
                      <button className="generation-secondary-action" type="button" onClick={closeModal}>
                        <X size={15} />
                        Cancel
                      </button>
                      <button className="generation-primary-action" type="submit" disabled={!canSaveSettings}>
                        <Check size={15} />
                        Save
                      </button>
                    </footer>
                  </form>
                ) : null}

                {modal.type === "edit" ? (
                  <form
                    className="generation-dialog generation-edit-dialog"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="generation-edit-title"
                    onSubmit={saveSessionTitle}
                    ref={(node) => {
                      modalRef.current = node;
                    }}
                    tabIndex={-1}
                  >
                    <header>
                      <span className="generation-dialog-icon generation-edit-icon" aria-hidden="true">
                        <Settings size={30} />
                      </span>
                      <h2 id="generation-edit-title">Edit</h2>
                      <button className="generation-dialog-close generation-edit-close" type="button" aria-label="Close edit dialog" onClick={closeModal}>
                        <X size={20} />
                      </button>
                    </header>
                    <div className="generation-dialog-body">
                      <label className="generation-title-field generation-edit-title-field">
                        <span>Session Name</span>
                        <input
                          value={draftTitle}
                          onChange={(event) => setDraftTitle(event.target.value)}
                          placeholder={modalSession?.title || "New Session"}
                          autoFocus
                        />
                      </label>
                    </div>
                    <footer>
                      <button className="generation-secondary-action" type="button" onClick={closeModal}>
                        <X size={15} />
                        Cancel
                      </button>
                      <button className="generation-primary-action" type="submit">
                        <Check size={15} />
                        Save
                      </button>
                    </footer>
                  </form>
                ) : null}

                {modal.type === "delete" ? (
                  <section
                    className="generation-dialog danger generation-delete-dialog"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="generation-delete-title"
                    ref={(node) => {
                      modalRef.current = node;
                    }}
                    tabIndex={-1}
                  >
                    <header>
                      <span className="generation-dialog-icon generation-delete-icon" aria-hidden="true">
                        <Trash2 size={30} />
                      </span>
                      <h2 id="generation-delete-title">Delete</h2>
                      <button className="generation-dialog-close generation-delete-close" type="button" aria-label="Close delete dialog" onClick={closeModal}>
                        <X size={20} />
                      </button>
                    </header>
                    <div className="generation-dialog-body">
                      <div className="generation-delete-summary">
                        <span>Selected Session</span>
                        <strong>{modalSession?.title || "This session"}</strong>
                        <small>This local session history will be removed.</small>
                      </div>
                    </div>
                    <footer>
                      <button className="generation-secondary-action" type="button" onClick={closeModal}>
                        <X size={15} />
                        Cancel
                      </button>
                      <button className="generation-danger-action" type="button" onClick={deleteSession}>
                        <Trash2 size={15} />
                        Delete
                      </button>
                    </footer>
                  </section>
                ) : null}

                {modal.type === "delete-all" ? (
                  <section
                    className="generation-dialog danger generation-delete-dialog"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="generation-delete-all-title"
                    ref={(node) => {
                      modalRef.current = node;
                    }}
                    tabIndex={-1}
                  >
                    <header>
                      <span className="generation-dialog-icon generation-delete-icon" aria-hidden="true">
                        <Trash2 size={30} />
                      </span>
                      <h2 id="generation-delete-all-title">Delete All</h2>
                      <button className="generation-dialog-close generation-delete-close" type="button" aria-label="Close delete all dialog" onClick={closeModal}>
                        <X size={20} />
                      </button>
                    </header>
                    <div className="generation-dialog-body">
                      <div className="generation-delete-summary">
                        <span>Local History</span>
                        <strong>All Sessions</strong>
                        <small>Every local session in this browser will be removed.</small>
                      </div>
                    </div>
                    <footer>
                      <button className="generation-secondary-action" type="button" onClick={closeModal}>
                        <X size={15} />
                        No
                      </button>
                      <button className="generation-danger-action" type="button" onClick={deleteAllSessions}>
                        <Trash2 size={15} />
                        Yes
                      </button>
                    </footer>
                  </section>
                ) : null}
              </div>
            </div>,
            document.body
          )
        : null}
    </div>
  );
}

function newSession(): ChatSession {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "New Session",
    createdAt: now,
    updatedAt: now,
    messages: []
  };
}

function sanitizeSessions(value: ChatSession[]): ChatSession[] {
  return value
    .filter((session) => session && typeof session.id === "string")
    .map((session) => ({
      id: session.id,
      title: session.title || "New Session",
      createdAt: session.createdAt || new Date().toISOString(),
      updatedAt: session.updatedAt || session.createdAt || new Date().toISOString(),
      messages: Array.isArray(session.messages)
        ? session.messages
            .filter((message) => message && typeof message.content === "string")
            .map((message) => {
              const role: ChatMessage["role"] = message.role === "user" ? "user" : "assistant";
              const imageUrl = typeof message.imageUrl === "string" && !message.imageUrl.startsWith("data:")
                ? message.imageUrl
                : undefined;
              return {
                id: message.id || crypto.randomUUID(),
                role,
                content: message.content,
                createdAt: message.createdAt || session.updatedAt || new Date().toISOString(),
                imageUrl,
                imageFileName: message.imageFileName,
                traceUrl: message.traceUrl,
                provider: message.provider,
                agentId: message.agentId,
                capability: message.capability,
                candidateCount: message.candidateCount,
                roundCount: message.roundCount,
                selectedCandidateIndex: message.selectedCandidateIndex,
                model: message.model,
                quality: message.quality,
                costUsd: message.costUsd,
                latencyMs: message.latencyMs,
                error: message.error
              };
            })
        : []
    }));
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function titleFromPrompt(value: string) {
  const title = value.replace(/\s+/g, " ").trim();
  return title.length > 44 ? `${title.slice(0, 41)}...` : title || "New Session";
}

function isLevelOption(value: unknown): value is string {
  return typeof value === "string" && levelOptions.includes(value);
}

function messageMetaItems(message: ChatMessage) {
  const items: string[] = [];
  if (message.agentId) {
    items.push(message.agentId);
  }
  if (message.capability) {
    items.push(message.capability);
  }
  if (typeof message.candidateCount === "number" && message.candidateCount > 0) {
    items.push(`${message.candidateCount} candidates`);
  }
  if (typeof message.roundCount === "number" && message.roundCount > 0) {
    items.push(`${message.roundCount} rounds`);
  }
  if (typeof message.latencyMs === "number") {
    items.push(`${message.latencyMs.toFixed(0)} ms`);
  }
  if (typeof message.costUsd === "number") {
    items.push(`$${message.costUsd.toFixed(6)}`);
  }
  return items;
}

function getFocusableElements(container: HTMLElement | null) {
  if (!container) {
    return [];
  }

  return Array.from(container.querySelectorAll<HTMLElement>(modalFocusableSelector)).filter((element) => {
    const ariaHidden = element.getAttribute("aria-hidden") === "true";
    return !ariaHidden && (element.offsetWidth > 0 || element.offsetHeight > 0 || element.getClientRects().length > 0);
  });
}

function firstFocusableElement(container: HTMLElement | null) {
  return getFocusableElements(container)[0] || null;
}
