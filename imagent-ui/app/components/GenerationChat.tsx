"use client";

import { FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  BadgeCheck,
  Check,
  ChevronDown,
  Clapperboard,
  CornerDownLeft,
  Download,
  Eraser,
  FileJson,
  ImageIcon,
  KeyRound,
  LayoutDashboard,
  Loader2,
  MessageSquarePlus,
  RadioTower,
  Send,
  Settings,
  Sparkles,
  Trash2,
  Workflow,
  X
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
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

const starterPrompts: Array<{ icon: LucideIcon; label: string; prompt: string; title: string }> = [
  {
    icon: Clapperboard,
    label: "Poster",
    title: "Cinematic Leaderboard",
    prompt: "Create a cinematic square poster for an open-source image agent leaderboard."
  },
  {
    icon: BadgeCheck,
    label: "Badge",
    title: "Benchmark Pass",
    prompt: "Design a clean benchmark pass badge with a green check mark."
  },
  {
    icon: LayoutDashboard,
    label: "Card",
    title: "Contribution Dashboard",
    prompt: "Generate a product card for a miner contribution dashboard."
  },
  {
    icon: Workflow,
    label: "Diagram",
    title: "PR Automation",
    prompt: "Make a polished visual explaining PR benchmark automation."
  }
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
  const settingsButtonRef = useRef<HTMLButtonElement | null>(null);
  const settingsCloseButtonRef = useRef<HTMLButtonElement | null>(null);
  const settingsModalRef = useRef<HTMLElement | null>(null);
  const settingsTriggerRef = useRef<HTMLElement | null>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const refocusPrompt = useRef(false);

  // Grow the textarea with its content instead of shipping a native resize grip,
  // and hand focus back to it whenever the prompt is filled or cleared for the user.
  useLayoutEffect(() => {
    const textarea = promptRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
    if (refocusPrompt.current) {
      refocusPrompt.current = false;
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }
  }, [prompt]);

  function applyStarterPrompt(value: string) {
    refocusPrompt.current = true;
    setPrompt(value);
  }

  function clearPrompt() {
    refocusPrompt.current = true;
    setPrompt("");
  }

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
  const promptLength = prompt.trim().length;
  const canCreateNewSession = !activeSession || activeSession.messages.length > 0 || prompt.trim().length > 0;
  const activeMessages = activeSession?.messages || [];
  const latestAgentMessage = [...activeMessages].reverse().find((message) => message.role === "agent");
  const latestUserMessage = [...activeMessages].reverse().find((message) => message.role === "user");
  const recentSessions = sessions.filter((session) => session.messages.length > 0).slice(0, 5);
  const runtimeState = !runtimeStatus && !runtimeError ? "checking" : runtimeReady ? "ready" : "blocked";
  const stageState = isGenerating
    ? "running"
    : latestAgentMessage?.imageUrl
      ? "ready"
      : latestAgentMessage?.error
        ? "error"
        : "empty";
  // Labelled tiles instead of an unlabelled chip row: a bare "auto" or a bare model id
  // told the user nothing, and two identical values collided as React keys.
  const latestMetaTiles: Array<{ label: string; value: string }> = [];

  if (latestAgentMessage?.latencyMs !== undefined) {
    latestMetaTiles.push({ label: "Latency", value: `${latestAgentMessage.latencyMs.toFixed(0)} ms` });
  }
  if (latestAgentMessage?.costUsd !== undefined) {
    latestMetaTiles.push({ label: "Cost", value: `$${latestAgentMessage.costUsd.toFixed(6)}` });
  }
  if (latestAgentMessage?.quality) {
    latestMetaTiles.push({ label: "Quality", value: latestAgentMessage.quality });
  }
  if (typeof latestAgentMessage?.candidateCount === "number" && latestAgentMessage.candidateCount > 0) {
    latestMetaTiles.push({ label: "Candidates", value: String(latestAgentMessage.candidateCount) });
  }
  if (typeof latestAgentMessage?.roundCount === "number" && latestAgentMessage.roundCount > 0) {
    latestMetaTiles.push({ label: "Rounds", value: String(latestAgentMessage.roundCount) });
  }

  const latestMetaFooter: string[] = [];

  if (latestAgentMessage?.agentId) {
    latestMetaFooter.push(latestAgentMessage.agentId);
  }
  if (latestAgentMessage?.capability) {
    latestMetaFooter.push(latestAgentMessage.capability);
  }
  if (latestAgentMessage) {
    latestMetaFooter.push(latestAgentMessage.model || settings.model);
  }

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

  function deleteSession(id: string) {
    setSessions((current) => {
      const next = current.filter((session) => session.id !== id);
      if (!next.length) {
        const replacement = newSession();
        setActiveSessionId(replacement.id);
        return [replacement];
      }
      if (activeSessionId === id) {
        setActiveSessionId(next[0].id);
      }
      return next;
    });
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
    <div className="generation-shell">
      <LandingBackgroundFx />
      <ScrollReveal />
      <section className="generation-hero" aria-labelledby="generation-title" data-reveal="fade-up">
        <div className="generation-hero-copy">
          <span className="generation-kicker">
            <Sparkles size={14} />
            Image Agent Console
          </span>
          <h1 id="generation-title">Generate With The Current Agent</h1>
          <p>
            Write one prompt and let Imagent call the fixed OpenRouter image model through the current agent runtime.
          </p>
        </div>

        <div className="generation-console-rail">
          <div className="generation-status-row" aria-label="Generation status">
            <span className={`generation-status-pill ${runtimeState}`}>
              <span className="generation-status-dot" />
              {runtimeState === "checking" ? "Checking Runtime" : runtimeReady ? "Runtime Ready" : "Runtime Blocked"}
            </span>
            {hasConfiguredOpenRouter ? (
              <span className="generation-status-pill ready">
                <KeyRound size={14} />
                OpenRouter Ready
              </span>
            ) : (
              // The one status that the user can act on, so it is the one that is a button.
              <button className="generation-status-pill warning actionable" type="button" onClick={openSettings}>
                <KeyRound size={14} />
                OpenRouter Needed
              </button>
            )}
            <span className="generation-status-pill">
              <RadioTower size={14} />
              Gittensor Powered
            </span>
          </div>
          <button className="generation-settings-button" type="button" onClick={openSettings} ref={settingsButtonRef}>
            <Settings size={17} />
            Settings
          </button>
        </div>
      </section>

      <section className="generation-workspace" aria-label="Generation workspace">
        <div className="generation-panel generation-prompt-panel">
          <div className="generation-panel-head">
            <div>
              <span>Prompt</span>
              <strong>{activeSession?.title || "New Run"}</strong>
            </div>
            <button className="generation-new-run" type="button" onClick={createSession} disabled={!canCreateNewSession}>
              <MessageSquarePlus size={16} />
              New Run
            </button>
          </div>

          <div className="generation-model-card">
            <div>
              <span>
                <Sparkles size={15} />
                Model
              </span>
              <strong>{selectedComposerModel?.name || labelForModel(settings.model, composerModelChoices)}</strong>
            </div>
            <small>Fixed through OpenRouter so agent logic is the variable.</small>
          </div>

          <div className="generation-composer-wrap">
            <form className="generation-composer" onSubmit={submit}>
              <textarea
                ref={promptRef}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Describe the image you want the agent to plan and generate"
                aria-describedby="composer-hint"
                rows={1}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div className="composer-hint" id="composer-hint">
                <span className="composer-hint-keys">
                  <kbd>
                    <CornerDownLeft size={11} />
                    Enter
                  </kbd>
                  to generate
                  <kbd>Shift + Enter</kbd>
                  for a new line
                </span>
                {promptLength > 0 ? (
                  <span className="composer-hint-actions">
                    <span className="composer-count">{promptLength.toLocaleString()} characters</span>
                    <button className="composer-clear-button" type="button" onClick={clearPrompt}>
                      <Eraser size={13} />
                      Clear
                    </button>
                  </span>
                ) : null}
              </div>
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

          <div className="generation-suggestions">
            <div className="generation-suggestions-head">
              <span>
                <Sparkles size={13} />
                Starter Prompts
              </span>
              <small>Click to fill the composer</small>
            </div>
            <div className="prompt-suggestions">
              {starterPrompts.map((item, index) => {
                const Icon = item.icon;
                const applied = prompt.trim() === item.prompt;
                return (
                  <div
                    className="starter-card-shell"
                    data-reveal="fade-up"
                    data-reveal-delay={index + 1}
                    key={item.title}
                  >
                    <EffectCard className={applied ? "starter-card applied" : "starter-card"} glareOpacity={0.12} radius={18}>
                      <button type="button" aria-pressed={applied} onClick={() => applyStarterPrompt(item.prompt)}>
                        <span className="starter-card-head">
                          <span className="starter-card-index">{String(index + 1).padStart(2, "0")}</span>
                          <span className="starter-card-icon">
                            {applied ? <Check size={16} /> : <Icon size={16} />}
                          </span>
                        </span>
                        <span className="starter-card-label">{item.label}</span>
                        <strong>{item.title}</strong>
                        <small>{item.prompt}</small>
                      </button>
                    </EffectCard>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="generation-panel generation-preview-panel">
          <div className="generation-panel-head">
            <div>
              <span>Preview</span>
              <strong>Latest Agent Output</strong>
            </div>
            <span className={isGenerating ? "generation-preview-badge running" : "generation-preview-badge"}>
              {isGenerating ? "Running" : latestAgentMessage?.imageUrl ? "Ready" : "Waiting"}
            </span>
          </div>

          <div className="generation-preview-surface">
            {/* One square stage that never changes size, so the panel does not jump between states. */}
            <div className="generation-stage" data-state={stageState}>
              <span className="generation-stage-frame" aria-hidden="true" />
              {isGenerating ? (
                <div className="generation-preview-state generation-preview-loading">
                  <Loader2 className="spin" size={30} />
                  <strong>Agent Is Generating</strong>
                  <p>Planning the prompt and calling the OpenRouter image model.</p>
                  <span className="generation-stage-progress" role="progressbar" aria-label="Generating image">
                    <span />
                  </span>
                </div>
              ) : latestAgentMessage?.imageUrl ? (
                <div className="generation-stage-image">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={latestAgentMessage.imageUrl} alt="Generated image" />
                </div>
              ) : latestAgentMessage?.error ? (
                <div className="generation-preview-state generation-preview-error">
                  <AlertCircle size={30} />
                  <strong>Generation Failed</strong>
                  <p>{latestAgentMessage.error}</p>
                </div>
              ) : (
                <div className="generation-preview-state generation-preview-empty">
                  <div className="generation-preview-orb">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/brand/imagent-ai-avatar.jpg" alt="" />
                  </div>
                  <strong>Image Preview</strong>
                  <p>Your generated image and trace will appear here after the agent run.</p>
                </div>
              )}
            </div>

            {latestAgentMessage?.imageUrl ? (
              <div className="generation-preview-result">
                {latestUserMessage ? (
                  <div className="generation-latest-prompt">
                    <span>Prompt</span>
                    <p>{latestUserMessage.content}</p>
                  </div>
                ) : null}
                {latestMetaTiles.length > 0 ? (
                  <div className="generation-preview-meta">
                    {latestMetaTiles.map((tile) => (
                      <div className="generation-meta-tile" key={tile.label}>
                        <span>{tile.label}</span>
                        <strong>{tile.value}</strong>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="generation-preview-actions">
                  <a href={latestAgentMessage.imageUrl} download={latestAgentMessage.imageFileName || "imagent-output.png"}>
                    <Download size={15} />
                    Download Image
                  </a>
                  {latestAgentMessage.traceUrl ? (
                    <a href={latestAgentMessage.traceUrl} target="_blank" rel="noreferrer">
                      <FileJson size={15} />
                      View Trace
                    </a>
                  ) : null}
                </div>
                {latestMetaFooter.length > 0 ? (
                  <p className="generation-preview-provenance">{latestMetaFooter.join(" · ")}</p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <section className="generation-runs" aria-label="Recent runs">
        <div className="generation-runs-head">
          <div>
            <span>Recent Runs</span>
            <strong>Saved In This Browser</strong>
          </div>
          <small>{recentSessions.length} active</small>
        </div>
        {recentSessions.length > 0 ? (
          <div className="generation-run-list">
            {recentSessions.map((session) => {
              const active = session.id === activeSessionId;
              const images = session.messages.filter((message) => Boolean(message.imageUrl)).length;
              // No data-reveal here: ScrollReveal only observes elements that exist at
              // mount, and run cards are created after a generation.
              return (
                <div className="generation-run-shell" key={session.id}>
                  <EffectCard className={active ? "generation-run-card active" : "generation-run-card"} glareOpacity={0.1} radius={18}>
                    <button
                      className="generation-run-select"
                      type="button"
                      aria-current={active}
                      onClick={() => setActiveSessionId(session.id)}
                    >
                      <span className="generation-run-mark" aria-hidden="true">
                        {active ? <RadioTower size={14} /> : <ImageIcon size={14} />}
                      </span>
                      <span className="generation-run-copy">
                        <strong>{session.title}</strong>
                        <span>
                          {images > 0 ? `${images} image${images === 1 ? "" : "s"}` : "No image yet"}
                          {" · "}
                          {formatRelativeTime(session.updatedAt)}
                        </span>
                      </span>
                    </button>
                    <button
                      className="generation-run-delete"
                      type="button"
                      aria-label={`Delete ${session.title}`}
                      onClick={() => deleteSession(session.id)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </EffectCard>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="generation-runs-empty">
            <ImageIcon size={18} />
            <p>No saved runs yet. Your generations are stored in this browser only.</p>
          </div>
        )}
      </section>

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

function formatRelativeTime(value: string) {
  const then = new Date(value).getTime();
  if (!Number.isFinite(then)) {
    return "just now";
  }
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) {
    return "just now";
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  return `${Math.round(hours / 24)}d ago`;
}

function titleFromPrompt(prompt: string) {
  return prompt.length > 42 ? `${prompt.slice(0, 42)}...` : prompt;
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
