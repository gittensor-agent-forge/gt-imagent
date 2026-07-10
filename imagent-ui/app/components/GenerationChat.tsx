"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  BadgeCheck,
  Check,
  ChevronDown,
  Clock3,
  Coins,
  Download,
  FileJson,
  Gauge,
  KeyRound,
  LayoutGrid,
  Loader2,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  RadioTower,
  RefreshCw,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wand2,
  X
} from "lucide-react";
import { EffectCard, LandingBackgroundFx } from "@/app/components/EffectCard";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import {
  IMAGENT_GENERATION_MODEL_ID,
  IMAGENT_GENERATION_MODEL_OPTION,
  IMAGENT_GENERATION_MODEL_NAME
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

const starterCards = [
  {
    id: "poster",
    icon: Sparkles,
    label: "Poster",
    title: "Cinematic leaderboard",
    prompt: "Create a cinematic square poster for an open-source image agent leaderboard."
  },
  {
    id: "badge",
    icon: BadgeCheck,
    label: "Badge",
    title: "Benchmark pass mark",
    prompt: "Design a clean benchmark pass badge with a green check mark."
  },
  {
    id: "dashboard",
    icon: LayoutGrid,
    label: "Product",
    title: "Miner dashboard card",
    prompt: "Generate a product card for a miner contribution dashboard."
  },
  {
    id: "automation",
    icon: Wand2,
    label: "Explain",
    title: "PR automation visual",
    prompt: "Make a polished visual explaining PR benchmark automation."
  }
] as const;

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
  const [isCheckingRuntime, setIsCheckingRuntime] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [railOpen, setRailOpen] = useState(true);
  const [selectedStarterId, setSelectedStarterId] = useState<string | null>(null);
  const committedSettingsRef = useRef(settings);
  const settingsButtonRef = useRef<HTMLButtonElement | null>(null);
  const settingsCloseButtonRef = useRef<HTMLButtonElement | null>(null);
  const settingsModalRef = useRef<HTMLElement | null>(null);
  const settingsTriggerRef = useRef<HTMLElement | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const apiKeyInputRef = useRef<HTMLInputElement | null>(null);

  async function loadRuntimeStatus() {
    setIsCheckingRuntime(true);
    try {
      const response = await fetch("/api/playground/status", { cache: "no-store" });
      const data = (await response.json()) as RuntimeStatusResponse;
      setRuntimeStatus(data);
      setRuntimeError("");
    } catch (error) {
      setRuntimeStatus(null);
      setRuntimeError(error instanceof Error ? error.message : "Failed to check the Imagent runtime.");
    } finally {
      setIsCheckingRuntime(false);
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
    const textarea = composerTextareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 280)}px`;
  }, [prompt]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    const fallbackSettingsButton = settingsButtonRef.current;
    const focusTimer = window.setTimeout(() => {
      const focusTarget = apiKeyInputRef.current || firstFocusableElement(settingsModalRef.current) || settingsModalRef.current;
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
  const latestAgentMessage = [...activeMessages].reverse().find((message) => message.role === "agent");
  const latestUserMessage = [...activeMessages].reverse().find((message) => message.role === "user");
  const runtimeState = !runtimeStatus && !runtimeError ? "checking" : runtimeReady ? "ready" : "blocked";
  const runtimeIssues = runtimeError
    ? [runtimeError]
    : (runtimeStatus?.issues || []).filter((issue) => typeof issue === "string" && issue.trim().length > 0);
  const previewHasImage = Boolean(latestAgentMessage?.imageUrl);
  const previewFailed = !isGenerating && !previewHasImage && Boolean(latestAgentMessage?.error);
  const previewBadgeLabel = isGenerating ? "Running" : previewHasImage ? "Ready" : previewFailed ? "Failed" : "Waiting";
  const previewBadgeClass = `generation-preview-badge${isGenerating ? " running" : previewFailed ? " failed" : previewHasImage ? " ready" : ""}`;
  const savedRuns = sessions.filter((session) => session.messages.length > 0);
  const resultMetrics = [
    latestAgentMessage?.agentId ? { icon: Sparkles, label: "Agent", value: latestAgentMessage.agentId } : null,
    latestAgentMessage?.capability ? { icon: Gauge, label: "Capability", value: latestAgentMessage.capability } : null,
    latestAgentMessage?.model || settings.model
      ? { icon: RadioTower, label: "Model", value: latestAgentMessage?.model || settings.model }
      : null,
    latestAgentMessage?.quality ? { icon: LayoutGrid, label: "Quality", value: latestAgentMessage.quality } : null,
    typeof latestAgentMessage?.latencyMs === "number"
      ? { icon: Clock3, label: "Latency", value: `${latestAgentMessage.latencyMs.toFixed(0)} ms` }
      : null,
    typeof latestAgentMessage?.costUsd === "number"
      ? { icon: Coins, label: "Cost", value: `$${latestAgentMessage.costUsd.toFixed(6)}` }
      : null,
    typeof latestAgentMessage?.candidateCount === "number" && latestAgentMessage.candidateCount > 0
      ? { icon: LayoutGrid, label: "Candidates", value: String(latestAgentMessage.candidateCount) }
      : null,
    typeof latestAgentMessage?.roundCount === "number" && latestAgentMessage.roundCount > 0
      ? { icon: Gauge, label: "Rounds", value: String(latestAgentMessage.roundCount) }
      : null
  ].filter((metric): metric is { icon: typeof Sparkles; label: string; value: string } => metric !== null);

  function createSession() {
    if (!canCreateNewSession && activeSession) {
      setActiveSessionId(activeSession.id);
      return;
    }

    const session = newSession();
    setSessions((current) => [session, ...current]);
    setActiveSessionId(session.id);
    setPrompt("");
    setSelectedStarterId(null);
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

  function applyStarterPrompt(card: (typeof starterCards)[number]) {
    setSelectedStarterId(card.id);
    setPrompt(card.prompt);
    window.requestAnimationFrame(() => {
      const textarea = composerTextareaRef.current;
      if (!textarea) {
        return;
      }
      textarea.focus({ preventScroll: true });
      const end = card.prompt.length;
      textarea.setSelectionRange(end, end);
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 280)}px`;
    });
  }

  function clearPrompt() {
    setPrompt("");
    setSelectedStarterId(null);
    composerTextareaRef.current?.focus({ preventScroll: true });
  }

  function selectSession(sessionId: string) {
    const session = sessions.find((item) => item.id === sessionId);
    const lastUser = session ? latestUserMessageFor(session) : undefined;
    setActiveSessionId(sessionId);
    setPrompt(lastUser?.content || "");
    setSelectedStarterId(null);
    window.requestAnimationFrame(() => {
      const textarea = composerTextareaRef.current;
      if (!textarea) {
        return;
      }
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 280)}px`;
    });
  }

  function deleteSession(sessionId: string) {
    setSessions((current) => {
      const next = current.filter((session) => session.id !== sessionId);
      if (!next.length) {
        const fresh = newSession();
        setActiveSessionId(fresh.id);
        setPrompt("");
        setSelectedStarterId(null);
        return [fresh];
      }
      if (activeSessionId === sessionId) {
        const replacement = next[0];
        setActiveSessionId(replacement.id);
        const lastUser = latestUserMessageFor(replacement);
        setPrompt(lastUser?.content || "");
        setSelectedStarterId(null);
      }
      return next;
    });
  }

  function runStatusFor(session: ChatSession): "ready" | "failed" | "waiting" {
    const agent = latestAgentMessageFor(session);
    if (!agent) {
      return "waiting";
    }
    if (agent.error) {
      return "failed";
    }
    if (agent.imageUrl) {
      return "ready";
    }
    return "waiting";
  }

  function formatRelativeTime(value: string) {
    const deltaMs = Date.now() - new Date(value).getTime();
    const minutes = Math.max(1, Math.round(deltaMs / 60000));
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
    const hours = Math.round(minutes / 60);
    if (hours < 48) {
      return `${hours}h ago`;
    }
    const days = Math.round(hours / 24);
    return `${days}d ago`;
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
    setSelectedStarterId(null);
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
    <div className="imagent-landing generation-shell generation-studio">
      <LandingBackgroundFx />
      <ScrollReveal />

      <header className="generation-studio-header" data-reveal="fade-up">
        <div className="generation-studio-header-copy">
          <span className="generation-kicker">
            <Sparkles size={14} />
            Agent Bench Console
          </span>
          <div className="generation-studio-title-row">
            <h1 id="generation-title">Generation Studio</h1>
            <p>Run the current agent against the fixed OpenRouter image model.</p>
          </div>
        </div>
        <div className="generation-studio-header-rail" aria-label="Generation status">
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
            <button className="generation-status-pill warning generation-status-action" type="button" onClick={openSettings}>
              <KeyRound size={14} />
              OpenRouter Needed
            </button>
          )}
          <span className="generation-status-pill">
            <RadioTower size={14} />
            Gittensor Powered
          </span>
          <button className="generation-settings-button" type="button" onClick={openSettings} ref={settingsButtonRef}>
            <Settings size={17} />
            Settings
          </button>
        </div>
      </header>

      <div className="generation-studio-bench-strip" data-reveal="fade-up" data-reveal-delay="1">
        <EffectCard animated className="generation-studio-bench-card" radius={17} glareOpacity={0.1}>
          <Sparkles size={17} />
          <span>Model</span>
          <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong>
        </EffectCard>
        <EffectCard animated className="generation-studio-bench-card" radius={17} glareOpacity={0.1}>
          <ShieldCheck size={17} />
          <span>Bench Rule</span>
          <strong>Agent Is The Variable</strong>
        </EffectCard>
      </div>

      {runtimeState === "blocked" ? (
        <div className="generation-runtime-alert" role="alert" data-reveal="fade-up" data-reveal-delay="1">
          <span className="generation-runtime-alert-icon" aria-hidden="true">
            <AlertCircle size={18} />
          </span>
          <div className="generation-runtime-alert-copy">
            <strong>Runtime Blocked</strong>
            {runtimeIssues.length > 0 ? (
              <ul>
                {runtimeIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : (
              <p>The Imagent runtime is not ready, so generation stays disabled.</p>
            )}
          </div>
          <button
            className="generation-runtime-retry"
            type="button"
            onClick={() => void loadRuntimeStatus()}
            disabled={isCheckingRuntime}
          >
            {isCheckingRuntime ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
            {isCheckingRuntime ? "Checking" : "Retry Check"}
          </button>
        </div>
      ) : null}

      <section className="generation-studio-grid" aria-label="Generation workspace" data-reveal="fade-up" data-reveal-delay="2">
        <aside className={`generation-studio-rail ${railOpen ? "is-open" : "is-collapsed"}`} aria-label="Saved runs">
          <div className="generation-studio-rail-head">
            <div>
              <span>Saved Runs</span>
              <strong>{savedRuns.length} total</strong>
            </div>
            <button
              className="generation-rail-toggle"
              type="button"
              aria-label={railOpen ? "Collapse run rail" : "Expand run rail"}
              onClick={() => setRailOpen((current) => !current)}
            >
              {railOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
            </button>
          </div>
          {railOpen ? (
            <>
              <button className="generation-new-run generation-studio-new-run" type="button" onClick={createSession} disabled={!canCreateNewSession}>
                <MessageSquarePlus size={16} />
                New Run
              </button>
              <div className="generation-studio-run-list custom-scrollbar">
                {savedRuns.length === 0 ? (
                  <p className="generation-studio-run-empty">Runs appear here after your first generation.</p>
                ) : (
                  savedRuns.map((session) => {
                    const isActive = session.id === activeSession?.id;
                    const runStatus = runStatusFor(session);
                    return (
                      <div className={`generation-studio-run-row ${isActive ? "is-active" : ""}`} key={session.id}>
                        <button
                          className={`generation-studio-run-card ${isActive ? "is-active" : ""}`}
                          type="button"
                          onClick={() => selectSession(session.id)}
                        >
                          <span className={`generation-run-status ${runStatus}`} aria-hidden="true" />
                          <span className="generation-studio-run-copy">
                            <strong>{session.title}</strong>
                            <small>{formatRelativeTime(session.updatedAt)}</small>
                          </span>
                        </button>
                        <button
                          className="generation-run-delete"
                          type="button"
                          aria-label={`Delete ${session.title}`}
                          onClick={() => deleteSession(session.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          ) : null}
        </aside>

        <div className="generation-studio-main">
          <EffectCard animated className="generation-studio-panel generation-studio-composer" radius={24} glareOpacity={0.12}>
            <div className="generation-panel-head">
              <div>
                <span>Prompt</span>
                <strong>{activeSession?.title || "New Run"}</strong>
              </div>
              <div className="generation-model-chip">
                <Sparkles size={15} />
                <span>{selectedComposerModel?.name || labelForModel(settings.model, composerModelChoices)}</span>
              </div>
            </div>

            <form className="generation-composer generation-studio-composer-form" onSubmit={submit}>
              <textarea
                ref={composerTextareaRef}
                value={prompt}
                onChange={(event) => {
                  const nextPrompt = event.target.value;
                  setPrompt(nextPrompt);
                  if (selectedStarterId && nextPrompt !== starterCards.find((card) => card.id === selectedStarterId)?.prompt) {
                    setSelectedStarterId(null);
                  }
                }}
                placeholder="Describe the image you want the current agent to plan and generate"
                rows={3}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div className="composer-hint-row">
                <small className="composer-keyboard-hint">
                  <kbd>Enter</kbd> generate · <kbd>Shift</kbd>+<kbd>Enter</kbd> new line
                </small>
                {prompt.length > 0 ? (
                  <div className="composer-hint-actions">
                    <small className="composer-char-count">{prompt.length} chars</small>
                    <button className="composer-clear-button" type="button" onClick={clearPrompt}>
                      Clear
                    </button>
                  </div>
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

            <div className="generation-studio-starters">
              <div className="generation-suggestions-head">
                <span>Starter Prompts</span>
                <small>Home card language</small>
              </div>
              <div className="generation-studio-starter-grid">
                {starterCards.map((card, index) => {
                  const Icon = card.icon;
                  const isSelected = selectedStarterId === card.id;
                  return (
                    <div data-reveal="fade-up" data-reveal-delay={index + 1} key={card.id}>
                      <EffectCard
                        animated={isSelected}
                        className={`generation-studio-starter-card ${isSelected ? "is-selected" : ""}`}
                        radius={20}
                        glareOpacity={0.1}
                      >
                      <button type="button" onClick={() => applyStarterPrompt(card)} aria-pressed={isSelected}>
                        <div className="generation-studio-starter-head">
                          <span>{String(index + 1).padStart(2, "0")}</span>
                          <Icon size={18} />
                        </div>
                        <small>{card.label}</small>
                        <strong>{card.title}</strong>
                        <p>{card.prompt}</p>
                      </button>
                    </EffectCard>
                    </div>
                  );
                })}
              </div>
            </div>
          </EffectCard>

          <EffectCard animated className="generation-studio-panel generation-studio-preview" radius={24} glareOpacity={0.12}>
            <div className="generation-panel-head">
              <div>
                <span>Preview</span>
                <strong>Agent Output</strong>
              </div>
              <span className={previewBadgeClass}>{previewBadgeLabel}</span>
            </div>

            <div className={`generation-preview-surface generation-studio-stage ${isGenerating ? "is-running" : previewFailed ? "is-failed" : previewHasImage ? "is-ready" : "is-empty"}`}>
              {isGenerating ? (
                <div className="generation-preview-state generation-preview-loading">
                  <Loader2 className="spin" size={30} />
                  <strong>Agent Is Generating</strong>
                  <p>Planning the prompt and calling the OpenRouter image model.</p>
                  <span className="generation-studio-progress" aria-hidden="true" />
                </div>
              ) : previewHasImage ? (
                <div className="generation-preview-result">
                  <div className="generation-preview-image generation-studio-preview-image">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={latestAgentMessage?.imageUrl} alt="Generated image" />
                  </div>
                </div>
              ) : previewFailed ? (
                <div className="generation-preview-state generation-preview-error">
                  <AlertCircle size={30} />
                  <strong>Generation Failed</strong>
                  <p>{latestAgentMessage?.error}</p>
                </div>
              ) : (
                <div className="generation-preview-state generation-preview-empty">
                  <div className="generation-preview-orb">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/brand/imagent-ai-avatar.jpg" alt="" />
                  </div>
                  <strong>Ready For Output</strong>
                  <p>Your generated image will render in this fixed stage.</p>
                </div>
              )}
            </div>

            {latestUserMessage ? (
              <div className="generation-latest-prompt generation-studio-latest-prompt">
                <span>Prompt</span>
                <p>{latestUserMessage.content}</p>
              </div>
            ) : null}

            {resultMetrics.length > 0 ? (
              <div className="generation-studio-metrics" aria-label="Run metrics">
                {resultMetrics.map((metric) => {
                  const Icon = metric.icon;
                  return (
                    <div className="generation-studio-metric" key={`${metric.label}-${metric.value}`}>
                      <span>
                        <Icon size={14} />
                        {metric.label}
                      </span>
                      <strong>{metric.value}</strong>
                    </div>
                  );
                })}
              </div>
            ) : null}

            {previewHasImage ? (
              <div className="generation-preview-actions">
                <a href={latestAgentMessage?.imageUrl} download={latestAgentMessage?.imageFileName || "imagent-output.png"}>
                  <Download size={15} />
                  Download Image
                </a>
                {latestAgentMessage?.traceUrl ? (
                  <a href={latestAgentMessage.traceUrl} target="_blank" rel="noreferrer">
                    <FileJson size={15} />
                    View Trace
                  </a>
                ) : null}
              </div>
            ) : null}
          </EffectCard>
        </div>
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
                      ref={apiKeyInputRef}
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

function latestAgentMessageFor(session: ChatSession) {
  return [...session.messages].reverse().find((message) => message.role === "agent");
}

function latestUserMessageFor(session: ChatSession) {
  return [...session.messages].reverse().find((message) => message.role === "user");
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
