"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  Check,
  ChevronDown,
  Download,
  FileJson,
  KeyRound,
  Loader2,
  MessageSquarePlus,
  Send,
  Settings,
  Sparkles,
  X
} from "lucide-react";
import { EffectCard, LandingBackgroundFx } from "@/app/components/EffectCard";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import {
  IMAGENT_GENERATION_MODEL_ID,
  IMAGENT_GENERATION_MODEL_OPTION
} from "@/lib/models";

type ChatMessage = {
  id: string;
  role: "user" | "agent";
  content: string;
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

type PlaygroundSettings = {
  apiKey: string;
  model: string;
  quality: string;
};

type SavedPlaygroundSettings = Omit<PlaygroundSettings, "apiKey">;

type OpenRouterModelOption = {
  id: string;
  name: string;
  description: string;
  pricing: string;
};

type VerificationStatus = "idle" | "verifying" | "valid" | "invalid";

type VerificationState = {
  status: VerificationStatus;
  message: string;
  models: OpenRouterModelOption[];
};

type VerificationCache = {
  cacheKey: string;
  message: string;
  models: OpenRouterModelOption[];
  verifiedAt: string;
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

type VerifyResponse = {
  verified?: boolean;
  key?: {
    label?: string;
    limit_remaining?: number | null;
  } | null;
  models?: OpenRouterModelOption[];
  usingServerKey?: boolean;
  warning?: string;
  error?: string;
};

const SESSIONS_KEY = "imagent.chatSessions";
const ACTIVE_SESSION_KEY = "imagent.activeSession";
const SETTINGS_KEY = "imagent.settings";
const LEGACY_VERIFICATION_CACHE_KEY = "imagent.openrouterVerification";

const defaultSettings: PlaygroundSettings = {
  apiKey: "",
  model: IMAGENT_GENERATION_MODEL_ID,
  quality: "auto"
};

const defaultSavedSettings: SavedPlaygroundSettings = {
  model: defaultSettings.model,
  quality: defaultSettings.quality
};

const fallbackModelOptions: OpenRouterModelOption[] = [
  {
    ...IMAGENT_GENERATION_MODEL_OPTION,
    pricing: "pricing loads after verification"
  }
];

const qualityOptions = ["auto", "low", "medium", "high"];

const emptyVerification: VerificationState = {
  status: "idle",
  message: "",
  models: []
};

const starterPrompts = [
  "Create a cinematic square poster for an open-source image agent leaderboard.",
  "Design a clean benchmark pass badge with a green check mark.",
  "Generate a product card for a miner contribution dashboard.",
  "Make a polished visual explaining PR benchmark automation."
];

const modalFocusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

export function GenerationChat() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [settings, setSettings] = useState<PlaygroundSettings>(defaultSettings);
  const [draftSettings, setDraftSettings] = useState<PlaygroundSettings>(defaultSettings);
  const [availableModels, setAvailableModels] = useState<OpenRouterModelOption[]>(fallbackModelOptions);
  const [verification, setVerification] = useState<VerificationState>(emptyVerification);
  const [verificationCache, setVerificationCache] = useState<VerificationCache | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusResponse | null>(null);
  const [runtimeError, setRuntimeError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<"composer-model" | "composer-quality" | null>(null);
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const committedSettingsRef = useRef(settings);
  const streamRef = useRef<HTMLDivElement | null>(null);
  const settingsButtonRef = useRef<HTMLButtonElement | null>(null);
  const settingsCloseButtonRef = useRef<HTMLButtonElement | null>(null);
  const settingsModalRef = useRef<HTMLElement | null>(null);
  const settingsTriggerRef = useRef<HTMLElement | null>(null);

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
    setIsMounted(true);
    const savedSessions = sanitizeSessions(readJson<ChatSession[]>(SESSIONS_KEY, []));
    const savedSettings = readJson<Partial<SavedPlaygroundSettings>>(SETTINGS_KEY, defaultSavedSettings);
    const initialSettings = {
      ...defaultSettings,
      model: defaultSettings.model,
      quality: isQualityOption(savedSettings.quality) ? savedSettings.quality : defaultSettings.quality
    };
    const initialSessions = savedSessions.length ? savedSessions : [newSession()];
    const savedActive = localStorage.getItem(ACTIVE_SESSION_KEY);
    const activeId = savedActive && initialSessions.some((session) => session.id === savedActive)
      ? savedActive
      : initialSessions[0].id;
    localStorage.removeItem(LEGACY_VERIFICATION_CACHE_KEY);
    setSessions(initialSessions);
    setActiveSessionId(activeId);
    setSettings(initialSettings);
    setDraftSettings(initialSettings);
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
    committedSettingsRef.current = settings;
  }, [settings]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    const fallbackSettingsButton = settingsButtonRef.current;
    const focusTimer = window.setTimeout(() => {
      const focusTarget = settingsCloseButtonRef.current || firstFocusableElement(settingsModalRef.current) || settingsModalRef.current;
      focusTarget?.focus({ preventScroll: true });
    }, 0);

    document.body.style.overflow = "hidden";

    function handleModalKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setDraftSettings(committedSettingsRef.current);
        setOpenDropdown(null);
        setSettingsOpen(false);
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const modal = settingsModalRef.current;
      if (!modal) {
        return;
      }

      const focusableElements = getFocusableElements(modal);
      if (!focusableElements.length) {
        event.preventDefault();
        modal.focus({ preventScroll: true });
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;
      if (event.shiftKey) {
        if (!modal.contains(activeElement) || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus({ preventScroll: true });
        }
        return;
      }

      if (!modal.contains(activeElement) || activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus({ preventScroll: true });
      }
    }

    window.addEventListener("keydown", handleModalKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleModalKeyDown);
      const trigger = settingsTriggerRef.current?.isConnected
        ? settingsTriggerRef.current
        : fallbackSettingsButton;
      if (trigger?.isConnected) {
        trigger.focus({ preventScroll: true });
      }
      settingsTriggerRef.current = null;
    };
  }, [settingsOpen]);

  useEffect(() => {
    const persistedSettings: SavedPlaygroundSettings = {
      model: settings.model,
      quality: settings.quality
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(persistedSettings));
  }, [settings.model, settings.quality]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }

    const apiKey = draftSettings.apiKey.trim();
    const cacheKey = apiKey ? `browser:${apiKey}` : runtimeStatus?.hasServerApiKey ? "server" : "";
    if (!cacheKey) {
      setVerification(emptyVerification);
      return;
    }

    if (isUsableVerificationCache(verificationCache, cacheKey)) {
      setAvailableModels(verificationCache.models);
      setVerification({
        status: "valid",
        message: verificationCache.message || "Verified",
        models: verificationCache.models
      });
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setVerification({ status: "verifying", message: "Checking key", models: [] });
      try {
        const response = await fetch("/api/openrouter/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(apiKey ? { apiKey } : {}),
          signal: controller.signal
        });
        const data = (await response.json()) as VerifyResponse;
        if (!response.ok || data.error) {
          throw new Error(data.error || `Verification failed with HTTP ${response.status}`);
        }

        const models = fixedModelOptions(data.models);
        const message = data.warning || (data.usingServerKey ? "Verified with the server key" : "Verified");
        const nextCache = {
          cacheKey,
          message,
          models,
          verifiedAt: new Date().toISOString()
        };
        setAvailableModels(models);
        setVerificationCache(nextCache);
        setVerification({
          status: "valid",
          message,
          models
        });
        setDraftSettings((current) => {
          const currentApiKey = current.apiKey.trim();
          if ((apiKey && currentApiKey !== apiKey) || (!apiKey && currentApiKey)) {
            return current;
          }
          return { ...current, model: IMAGENT_GENERATION_MODEL_ID };
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setVerification({
          status: "invalid",
          message: error instanceof Error ? error.message : "Verification failed",
          models: []
        });
      }
    }, 500);

    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [draftSettings.apiKey, runtimeStatus?.hasServerApiKey, settingsOpen, verificationCache]);

  const activeSession = sessions.find((session) => session.id === activeSessionId) || sessions[0];
  const hasServerApiKey = Boolean(runtimeStatus?.hasServerApiKey);
  const runtimeReady = Boolean(runtimeStatus?.ready);
  const hasConfiguredOpenRouter = hasServerApiKey || settings.apiKey.trim().length > 0;
  const draftApiKey = draftSettings.apiKey.trim();
  const draftUsesServerKey = !draftApiKey && hasServerApiKey;
  const keyModeLabel = draftApiKey ? "Browser key" : hasServerApiKey ? "Server key" : "Key needed";
  const apiKeyControlClass = verification.status === "idle" ? "api-key-control" : `api-key-control has-status ${verification.status}`;
  const modelChoices = verification.models.length ? verification.models : availableModels;
  const canSaveSettings = (!draftApiKey && !draftUsesServerKey) || verification.status === "valid";
  const settingsModelOption = modelChoices.find((model) => model.id === IMAGENT_GENERATION_MODEL_ID) || fallbackModelOptions[0];
  const composerModelChoices = availableModels.length ? availableModels : fallbackModelOptions;
  const selectedComposerModel = composerModelChoices.find((model) => model.id === settings.model);
  const canSubmit = useMemo(() => prompt.trim().length > 0 && !isGenerating && runtimeReady, [prompt, isGenerating, runtimeReady]);
  const canCreateNewSession = !activeSession || activeSession.messages.length > 0 || prompt.trim().length > 0;
  const activeMessages = activeSession?.messages || [];
  const activeMessageCount = activeMessages.length;
  const latestAgentMessage = [...activeMessages].reverse().find((message) => message.role === "agent");
  const runtimeState = !runtimeStatus && !runtimeError ? "checking" : runtimeReady ? "ready" : "blocked";

  useEffect(() => {
    const stream = streamRef.current;
    if (stream) {
      stream.scrollTop = stream.scrollHeight;
    }
  }, [activeSessionId, activeMessageCount, isGenerating]);

  function createSession() {
    if (!canCreateNewSession && activeSession) {
      setActiveSessionId(activeSession.id);
      return;
    }

    const session = newSession();
    setSessions((current) => [session, ...current]);
    setActiveSessionId(session.id);
    setPrompt("");
  }

  function saveSettings() {
    const nextSettings = {
      apiKey: draftSettings.apiKey.trim(),
      model: IMAGENT_GENERATION_MODEL_ID,
      quality: draftSettings.quality
    };
    if (!nextSettings.apiKey && !hasServerApiKey) {
      setVerification(emptyVerification);
      setVerificationCache(null);
    }
    setSettings(nextSettings);
    setOpenDropdown(null);
    setSettingsOpen(false);
  }

  function openSettings() {
    const activeElement = document.activeElement;
    settingsTriggerRef.current = activeElement instanceof HTMLElement && activeElement !== document.body
      ? activeElement
      : settingsButtonRef.current;
    setDraftSettings(settings);
    setOpenDropdown(null);
    setSettingsOpen(true);
    void loadRuntimeStatus();
  }

  function cancelSettings() {
    setDraftSettings(settings);
    setOpenDropdown(null);
    setSettingsOpen(false);
  }

  function updateComposerModel(model: string) {
    setSettings((current) => ({...current, model: model === IMAGENT_GENERATION_MODEL_ID ? model : IMAGENT_GENERATION_MODEL_ID}));
    setOpenDropdown(null);
  }

  function updateComposerQuality(quality: string) {
    setSettings((current) => ({...current, quality}));
    setOpenDropdown(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !activeSession) {
      return;
    }
    if (!runtimeReady || !hasConfiguredOpenRouter) {
      openSettings();
      return;
    }

    const userPrompt = prompt.trim();
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: userPrompt
    };

    updateSession(activeSession.id, [userMessage], titleFromPrompt(userPrompt));
    setPrompt("");
    setIsGenerating(true);

    try {
      const response = await fetch("/api/playground/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          prompt: userPrompt,
          apiKey: settings.apiKey.trim() || undefined,
          quality: settings.quality
        })
      });
      const data = (await response.json()) as GenerateResponse;
      if (!response.ok || data.error) {
        throw new Error(data.error || `Generation failed with HTTP ${response.status}`);
      }
      updateSession(activeSession.id, [
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: "Generated with Imagent",
          imageUrl: data.imageUrl,
          imageFileName: data.imageFileName,
          traceUrl: data.traceUrl,
          provider: data.provider,
          agentId: data.agentId,
          capability: data.capability,
          candidateCount: data.candidateCount,
          roundCount: data.roundCount,
          selectedCandidateIndex: data.selectedCandidateIndex,
          model: data.model,
          quality: settings.quality,
          costUsd: data.costUsd,
          latencyMs: data.latencyMs
        }
      ]);
    } catch (error) {
      updateSession(activeSession.id, [
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: "Imagent generation failed",
          error: error instanceof Error ? error.message : "Unknown generation error",
          model: settings.model
        }
      ]);
      void loadRuntimeStatus();
    } finally {
      setIsGenerating(false);
    }
  }

  function selectSession(sessionId: string) {
    setActiveSessionId(sessionId);
    setOpenDropdown(null);
  }

  function deleteSession(sessionId: string) {
    const remaining = sessions.filter((session) => session.id !== sessionId);
    const next = remaining.length ? remaining : [newSession()];
    setSessions(next);
    if (sessionId === activeSessionId) {
      setActiveSessionId(next[0].id);
      setPrompt("");
    }
  }

  function updateSession(sessionId: string, appendedMessages: ChatMessage[], nextTitle?: string) {
    setSessions((current) =>
      current.map((session) => {
        if (session.id !== sessionId) {
          return session;
        }
        return {
          ...session,
          title: session.title === "New chat" && nextTitle ? nextTitle : session.title,
          updatedAt: new Date().toISOString(),
          messages: [...session.messages, ...appendedMessages]
        };
      })
    );
  }

  return (
    <div className="imagent-landing generation-shell generation-studio-shell">
      <LandingBackgroundFx />
      <ScrollReveal />
      <div className="generation-studio" data-reveal="fade-up">
        <aside className="studio-sidebar" aria-label="Runs">
          <div className="studio-sidebar-head">
            <span className="studio-brand">
              <Sparkles size={16} />
              Image Studio
            </span>
            <button
              className="studio-new-run"
              type="button"
              onClick={createSession}
              disabled={!canCreateNewSession}
              title="Start a new run"
            >
              <MessageSquarePlus size={16} />
              New
            </button>
          </div>

          <div className="studio-session-list custom-scrollbar">
            {sessions.map((session) => {
              const imageCount = session.messages.filter(
                (message) => message.role === "agent" && message.imageUrl
              ).length;
              const isActive = session.id === activeSession?.id;
              return (
                <div className={isActive ? "studio-session active" : "studio-session"} key={session.id}>
                  <button className="studio-session-open" type="button" onClick={() => selectSession(session.id)}>
                    <span className="studio-session-title">{session.title}</span>
                    <span className="studio-session-meta">
                      {session.messages.length ? `${session.messages.length} messages` : "Empty run"}
                      {imageCount ? ` · ${imageCount} image${imageCount > 1 ? "s" : ""}` : ""}
                    </span>
                  </button>
                  {sessions.length > 1 ? (
                    <button
                      className="studio-session-delete"
                      type="button"
                      aria-label="Delete run"
                      title="Delete run"
                      onClick={() => deleteSession(session.id)}
                    >
                      <X size={14} />
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="studio-sidebar-foot">
            <div className="studio-status" aria-label="Generation status">
              <span className={`generation-status-pill ${runtimeState}`}>
                <span className="generation-status-dot" />
                {runtimeState === "checking" ? "Checking Runtime" : runtimeReady ? "Runtime Ready" : "Runtime Blocked"}
              </span>
              <span className={`generation-status-pill ${hasConfiguredOpenRouter ? "ready" : "warning"}`}>
                <KeyRound size={13} />
                {hasConfiguredOpenRouter ? "OpenRouter Ready" : "OpenRouter Needed"}
              </span>
            </div>
            <button className="studio-settings-button" type="button" onClick={openSettings} ref={settingsButtonRef}>
              <Settings size={16} />
              Settings
            </button>
          </div>
        </aside>

        <main className="studio-main">
          <header className="studio-main-head">
            <div className="studio-main-title">
              <span className="generation-kicker">
                <Sparkles size={13} />
                Image Agent Console
              </span>
              <strong>{activeSession?.title || "New Run"}</strong>
            </div>
            <div className="studio-main-tools">
              <span className="studio-model-chip" title={settings.model}>
                <Sparkles size={14} />
                {selectedComposerModel?.name || labelForModel(settings.model, composerModelChoices)}
              </span>
              <span className={isGenerating ? "generation-preview-badge running" : "generation-preview-badge"}>
                {isGenerating ? "Running" : latestAgentMessage?.imageUrl ? "Ready" : "Waiting"}
              </span>
            </div>
          </header>

          <div className="studio-stream custom-scrollbar" ref={streamRef}>
            {activeMessageCount === 0 && !isGenerating ? (
              <div className="studio-empty">
                <span className="studio-empty-orb" aria-hidden="true">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="/brand/imagent-ai-avatar.jpg" alt="" />
                </span>
                <h1>Generate With The Current Agent</h1>
                <p>Describe an image and the fixed OpenRouter model plans and renders it through the current agent runtime.</p>
                <div className="studio-starters">
                  {starterPrompts.map((item) => (
                    <button type="button" key={item} onClick={() => setPrompt(item)}>
                      <Sparkles size={14} />
                      <span>{item}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="studio-thread">
                {activeMessages.map((message) =>
                  message.role === "user" ? (
                    <div className="studio-turn studio-turn-user" key={message.id}>
                      <div className="studio-bubble">{message.content}</div>
                    </div>
                  ) : (
                    <div className="studio-turn studio-turn-agent" key={message.id}>
                      <span className="studio-turn-avatar" aria-hidden="true">
                        <Sparkles size={15} />
                      </span>
                      <div className="studio-turn-body">
                        {message.error ? (
                          <div className="studio-agent-error">
                            <AlertCircle size={18} />
                            <div>
                              <strong>Generation failed</strong>
                              <p>{message.error}</p>
                            </div>
                          </div>
                        ) : message.imageUrl ? (
                          <div className="studio-agent-result">
                            <div className="studio-agent-image">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={message.imageUrl} alt="Generated image" />
                            </div>
                            <div className="studio-agent-actions">
                              <a href={message.imageUrl} download={message.imageFileName || "imagent-output.png"}>
                                <Download size={14} />
                                Download
                              </a>
                              {message.traceUrl ? (
                                <a href={message.traceUrl} target="_blank" rel="noreferrer">
                                  <FileJson size={14} />
                                  Trace
                                </a>
                              ) : null}
                            </div>
                            {metaItemsForMessage(message, settings.model).length > 0 ? (
                              <div className="studio-agent-meta">
                                {metaItemsForMessage(message, settings.model).map((item, index) => (
                                  <span key={index}>{item}</span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ) : (
                          <div className="studio-bubble studio-bubble-agent">{message.content}</div>
                        )}
                      </div>
                    </div>
                  )
                )}
                {isGenerating ? (
                  <div className="studio-turn studio-turn-agent" key="generating">
                    <span className="studio-turn-avatar" aria-hidden="true">
                      <Loader2 className="spin" size={15} />
                    </span>
                    <div className="studio-turn-body">
                      <div className="studio-agent-generating">
                        <Loader2 className="spin" size={16} />
                        Planning the prompt and rendering the image
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div className="studio-composer-dock">
            <form className="generation-composer studio-composer" onSubmit={submit}>
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Describe the image you want the agent to plan and generate"
                rows={3}
                onKeyDown={(event) => {
                  if (event.nativeEvent.isComposing || event.keyCode === 229) {
                    return;
                  }
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div className="composer-toolbar">
                <div className="generation-composer-controls">
                  {hasConfiguredOpenRouter ? (
                    <>
                      <ModelDropdown
                        hideLabel
                        id="composer-model"
                        label="Model"
                        models={composerModelChoices}
                        open={openDropdown === "composer-model"}
                        selectedModel={settings.model}
                        selectedModelName={selectedComposerModel?.name || labelForModel(settings.model, composerModelChoices)}
                        onOpenChange={(open) => setOpenDropdown(open ? "composer-model" : null)}
                        onSelect={updateComposerModel}
                      />
                      <QualityDropdown
                        hideLabel
                        open={openDropdown === "composer-quality"}
                        selectedQuality={settings.quality}
                        onOpenChange={(open) => setOpenDropdown(open ? "composer-quality" : null)}
                        onSelect={updateComposerQuality}
                      />
                    </>
                  ) : (
                    <button className="composer-configure-button" type="button" onClick={openSettings}>
                      <KeyRound size={15} />
                      Configure OpenRouter
                    </button>
                  )}
                </div>
                <button className="composer-send-button" type="submit" disabled={!canSubmit} aria-label="Generate image">
                  {isGenerating ? (
                    <>
                      <Loader2 className="spin" size={16} />
                      Running
                    </>
                  ) : (
                    <>
                      <Send size={16} />
                      Generate
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>

      {settingsOpen && isMounted ? createPortal(
        <div
          className="modal-backdrop generation-settings-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              cancelSettings();
            }
          }}
        >
          <EffectCard animated className="settings-modal-card" glareOpacity={0.12} radius={24}>
            <section
              className="settings-modal custom-scrollbar"
              role="dialog"
              aria-modal="true"
              aria-labelledby="settings-title"
              ref={settingsModalRef}
              tabIndex={-1}
            >
              <header>
                <div className="settings-title-row">
                  <span className="settings-title-icon">
                    <Settings size={18} />
                  </span>
                  <div>
                    <h2 id="settings-title">Generation settings</h2>
                    <p>OpenRouter-backed image generation</p>
                  </div>
                </div>
                <div className="settings-header-actions">
                  <span className={`settings-key-pill ${verification.status}`}>
                    {keyModeLabel}
                  </span>
                  <button type="button" onClick={cancelSettings} aria-label="Close settings" ref={settingsCloseButtonRef}>
                    <X size={18} />
                  </button>
                </div>
              </header>
              <div className="settings-modal-body">
                <label className="settings-field settings-field--key">
                  <span>OpenRouter API key</span>
                  <div className={apiKeyControlClass}>
                    <KeyRound size={16} />
                    <input
                      type="password"
                      value={draftSettings.apiKey}
                      onChange={(event) => setDraftSettings({...draftSettings, apiKey: event.target.value})}
                      placeholder="sk-or-..."
                      autoComplete="off"
                    />
                    <VerificationBadge verification={verification} />
                  </div>
                  <small className="field-note">
                    {hasServerApiKey
                      ? "Leave blank to use the shared server key, or enter a browser key for this run."
                      : "Enter an OpenRouter key to generate images from this browser."}
                  </small>
                </label>
                <div className="settings-field">
                  <span>Image model</span>
                  <div className="fixed-model-card" aria-label="Fixed image model">
                    <Sparkles size={16} />
                    <span>
                      <strong>{settingsModelOption.name}</strong>
                      <small>{IMAGENT_GENERATION_MODEL_ID}</small>
                    </span>
                    <em>Fixed</em>
                  </div>
                  <small className="field-note">
                    {verification.status === "valid"
                      ? `${settingsModelOption.pricing || "pricing unavailable"} · fixed project model.`
                      : "Verify OpenRouter to confirm access and pricing."}
                  </small>
                </div>
                <div className="settings-field">
                  <span>Quality level</span>
                  <div className="segmented-control" role="radiogroup" aria-label="Quality level">
                    {qualityOptions.map((quality) => (
                      <button
                        className={draftSettings.quality === quality ? "active" : ""}
                        type="button"
                        role="radio"
                        aria-checked={draftSettings.quality === quality}
                        key={quality}
                        onClick={() => setDraftSettings({...draftSettings, quality})}
                      >
                        <span className="quality-check" aria-hidden="true">
                          {draftSettings.quality === quality ? <Check size={13} /> : null}
                        </span>
                        <span>{quality}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <footer>
                <button type="button" className="secondary-button" onClick={cancelSettings}>
                  Cancel
                </button>
                <button type="button" className="primary-button" onClick={saveSettings} disabled={!canSaveSettings}>
                  Save settings
                </button>
              </footer>
            </section>
          </EffectCard>
        </div>,
        document.body
      ) : null}
    </div>
  );
}

function ModelDropdown({
  disabled = false,
  emptyLabel = "No models loaded",
  hideLabel = false,
  id,
  label,
  models,
  onOpenChange,
  onSelect,
  open,
  selectedModel,
  selectedModelName
}: {
  disabled?: boolean;
  emptyLabel?: string;
  hideLabel?: boolean;
  id: string;
  label: string;
  models: OpenRouterModelOption[];
  onOpenChange: (open: boolean) => void;
  onSelect: (model: string) => void;
  open: boolean;
  selectedModel: string;
  selectedModelName: string;
}) {
  const selected = models.find((model) => model.id === selectedModel);
  const menuId = `${id}-menu`;

  return (
    <div
      className={`model-dropdown ${open ? "open" : ""} ${disabled ? "disabled" : ""}`}
      onBlur={(event) => {
        const nextFocus = event.relatedTarget as Node | null;
        if (!event.currentTarget.contains(nextFocus)) {
          onOpenChange(false);
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onOpenChange(false);
        }
      }}
    >
      <button
        className="model-dropdown-trigger"
        type="button"
        disabled={disabled}
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => onOpenChange(!open)}
      >
        <Sparkles size={15} />
        <span className="dropdown-copy">
          {hideLabel ? null : <small>{label}</small>}
          <strong>{disabled ? emptyLabel : selected?.name || selectedModelName}</strong>
        </span>
        <ChevronDown size={15} />
      </button>
      {open && !disabled ? (
        <div className="model-dropdown-menu custom-scrollbar" id={menuId} role="listbox" aria-label={label}>
          {models.map((model) => {
            const active = model.id === selectedModel;
            return (
              <button
                className={active ? "active" : ""}
                type="button"
                role="option"
                aria-selected={active}
                key={model.id}
                onClick={() => {
                  onSelect(model.id);
                  onOpenChange(false);
                }}
              >
                <span>
                  <strong>{model.name}</strong>
                  <small>{model.pricing || model.id}</small>
                </span>
                {active ? <Check size={15} /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function QualityDropdown({
  hideLabel = false,
  onOpenChange,
  onSelect,
  open,
  selectedQuality
}: {
  hideLabel?: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (quality: string) => void;
  open: boolean;
  selectedQuality: string;
}) {
  return (
    <div
      className={`quality-dropdown ${open ? "open" : ""}`}
      onBlur={(event) => {
        const nextFocus = event.relatedTarget as Node | null;
        if (!event.currentTarget.contains(nextFocus)) {
          onOpenChange(false);
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onOpenChange(false);
        }
      }}
    >
      <button
        className="quality-dropdown-trigger"
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => onOpenChange(!open)}
      >
        <span className="dropdown-copy">
          {hideLabel ? null : <small>Level</small>}
          <strong>{selectedQuality}</strong>
        </span>
        <ChevronDown size={15} />
      </button>
      {open ? (
        <div className="quality-dropdown-menu" role="listbox" aria-label="Generation level">
          {qualityOptions.map((quality) => {
            const active = quality === selectedQuality;
            return (
              <button
                className={active ? "active" : ""}
                type="button"
                role="option"
                aria-selected={active}
                key={quality}
                onClick={() => {
                  onSelect(quality);
                  onOpenChange(false);
                }}
              >
                <span>{quality}</span>
                {active ? <Check size={14} /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function VerificationBadge({ verification }: { verification: VerificationState }) {
  if (verification.status === "verifying") {
    return (
      <span className="verification-status verifying" aria-label="Verifying OpenRouter key" title="Verifying OpenRouter key">
        <Loader2 className="spin" size={14} />
      </span>
    );
  }

  if (verification.status === "valid") {
    return (
      <span className="verification-status valid" aria-label={verification.message || "OpenRouter key verified"} title={verification.message || "OpenRouter key verified"}>
        <Check size={14} />
      </span>
    );
  }

  if (verification.status === "invalid") {
    return (
      <span className="verification-status invalid" aria-label={verification.message || "Invalid OpenRouter key"} title={verification.message || "Invalid OpenRouter key"}>
        <AlertCircle size={14} />
      </span>
    );
  }

  return null;
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

function newSession(): ChatSession {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "New chat",
    createdAt: now,
    updatedAt: now,
    messages: []
  };
}

function titleFromPrompt(prompt: string) {
  return prompt.length > 42 ? `${prompt.slice(0, 42)}...` : prompt;
}

function metaItemsForMessage(message: ChatMessage, fallbackModel: string): string[] {
  const items: string[] = [];
  if (message.agentId) {
    items.push(message.agentId);
  }
  if (message.capability) {
    items.push(message.capability);
  }
  const model = message.model || fallbackModel;
  if (model) {
    items.push(model);
  }
  if (message.quality) {
    items.push(message.quality);
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

function labelForModel(model: string, models: OpenRouterModelOption[]) {
  const knownModel = models.find((option) => option.id === model);
  if (knownModel) {
    return knownModel.name.replace("Google ", "");
  }
  return model.length > 30 ? `${model.slice(0, 30)}...` : model;
}

function fixedModelOptions(models?: OpenRouterModelOption[]) {
  const discovered = models?.find((option) => option.id === IMAGENT_GENERATION_MODEL_ID);
  return [
    {
      ...fallbackModelOptions[0],
      ...(discovered || {}),
      id: IMAGENT_GENERATION_MODEL_ID
    }
  ];
}

function isUsableVerificationCache(cache: VerificationCache | null, cacheKey: string): cache is VerificationCache {
  return Boolean(cache && cache.cacheKey === cacheKey && Array.isArray(cache.models) && cache.models.length > 0);
}

function sanitizeSessions(sessions: ChatSession[]) {
  return sessions.map((session) => ({
    ...session,
    messages: session.messages.map((message) => {
      if (!message.imageUrl?.startsWith("data:")) {
        return message;
      }
      return {
        ...message,
        imageUrl: undefined,
        imageFileName: undefined
      };
    })
  }));
}

function isQualityOption(value: unknown): value is string {
  return typeof value === "string" && qualityOptions.includes(value);
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
