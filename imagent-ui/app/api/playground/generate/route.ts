import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";
import {
  BACKGROUND_OPTIONS,
  contentTypeForImage,
  DEFAULT_GENERATION_MODEL,
  getResolvedPlaygroundRuntime,
  pruneRunDirectories,
  QUALITY_OPTIONS,
  resolveRunDirectory,
  validateRunId,
  writeRunManifest
} from "@/lib/playground";
import {
  getClientIp,
  isRequestAuthorized,
  rateLimit,
  releaseGenerationSlot,
  tryAcquireGenerationSlot
} from "@/lib/security";
import { resolvePublicSiteUrl } from "@/lib/site";

type GenerateRequest = {
  prompt?: string;
  apiKey?: string;
  quality?: string;
  background?: string;
};

type AgentResult = {
  image_path?: string;
  trace_path?: string;
  metadata?: {
    agent_id?: string;
    candidate_count?: number;
    selected_candidate_index?: number;
    cost_usd?: number;
    latency_ms?: number;
    model?: string;
    provider?: string;
    media_type?: string;
  };
  agent_id?: string;
  capability?: string;
  candidate_count?: number;
  round_count?: number;
  selected_candidate_index?: number;
};

const execFileAsync = promisify(execFile);

// Abuse controls for this expensive, credit-consuming endpoint.
const GENERATION_TIMEOUT_MS = 120_000;
const MAX_CONCURRENT_GENERATIONS = 2;
const RATE_LIMIT_PER_MINUTE = 10;
const MAX_PROMPT_LENGTH = 4000;

async function parseJson<T>(request: Request): Promise<T | null> {
  try {
    return (await request.json()) as T;
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  const started = performance.now();

  if (!isRequestAuthorized(request)) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }

  const clientIp = getClientIp(request);
  const limit = rateLimit(`generate:${clientIp}`, RATE_LIMIT_PER_MINUTE);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: "Too many requests. Please slow down and try again shortly." },
      { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } }
    );
  }

  const body = await parseJson<GenerateRequest>(request);
  if (!body) {
    return NextResponse.json({ error: "Invalid JSON request body." }, { status: 400 });
  }

  const publicSiteUrl = resolvePublicSiteUrl();
  const prompt = String(body.prompt || "").trim();
  const model = DEFAULT_GENERATION_MODEL;
  const quality = String(body.quality || "auto").trim();
  const background = String(body.background || "auto").trim();

  if (!prompt) {
    return NextResponse.json({ error: "Prompt is required." }, { status: 400 });
  }
  if (prompt.length > MAX_PROMPT_LENGTH) {
    return NextResponse.json(
      { error: `Prompt must be ${MAX_PROMPT_LENGTH} characters or fewer.` },
      { status: 400 }
    );
  }
  if (!(QUALITY_OPTIONS as readonly string[]).includes(quality)) {
    return NextResponse.json({ error: "Unsupported quality option." }, { status: 400 });
  }
  if (!(BACKGROUND_OPTIONS as readonly string[]).includes(background)) {
    return NextResponse.json({ error: "Unsupported background option." }, { status: 400 });
  }

  const runtime = await getResolvedPlaygroundRuntime();
  const apiKey = String(body.apiKey || (runtime.hasServerApiKey ? process.env.OPENROUTER_API_KEY : "") || "").trim();

  if (!apiKey) {
    return NextResponse.json({ error: "OpenRouter API key is required." }, { status: 400 });
  }
  if (!runtime.ready) {
    return NextResponse.json(
      {
        error: runtime.issues.join(" ")
      },
      { status: 503 }
    );
  }

  if (!tryAcquireGenerationSlot(MAX_CONCURRENT_GENERATIONS)) {
    return NextResponse.json(
      { error: "The generation queue is busy. Please try again in a moment." },
      { status: 429 }
    );
  }

  const runId = `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  try {
    if (!validateRunId(runId)) {
      return NextResponse.json({ error: "Failed to allocate a valid run ID." }, { status: 500 });
    }
    const outputDir = resolveRunDirectory(runId);
    const requestPath = path.join(outputDir, "request.json");

    await fs.mkdir(outputDir, { recursive: true });
    await fs.writeFile(
      requestPath,
      JSON.stringify(
        {
          prompt,
          model,
          quality,
          background,
          public_site_url: publicSiteUrl,
          output_dir: outputDir,
          repository_path: runtime.repositoryPath,
          run_id: runId
        },
        null,
        2
      ),
      "utf8"
    );

    const { stdout, stderr } = await execFileAsync(runtime.pythonBin, ["scripts/run_imagent_agent.py", requestPath], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        OPENROUTER_API_KEY: apiKey
      },
      maxBuffer: 10 * 1024 * 1024,
      timeout: GENERATION_TIMEOUT_MS,
      killSignal: "SIGKILL"
    });
    if (stderr.trim()) {
      console.warn(stderr);
    }

    const agentResult = JSON.parse(stdout.trim()) as AgentResult;
    const imagePath = String(agentResult.image_path || "").trim();
    if (!imagePath) {
      throw new Error("Imagent agent did not return an image path.");
    }

    const mediaType = agentResult.metadata?.media_type || contentTypeForImage(imagePath);
    const imageExtension = path.extname(imagePath) || ".png";
    const imageFileName = `image${imageExtension.toLowerCase()}`;
    const storedImagePath = path.join(outputDir, imageFileName);
    await fs.copyFile(imagePath, storedImagePath);

    const tracePath = String(agentResult.trace_path || "").trim();
    const traceFileName = tracePath ? "trace.json" : null;
    if (tracePath && traceFileName) {
      await fs.copyFile(tracePath, path.join(outputDir, traceFileName));
    }
    await writeRunManifest(runId, {
      runId,
      imageFileName,
      imageMediaType: mediaType,
      traceFileName
    });

    return NextResponse.json({
      runId,
      imageUrl: `/api/playground/runs/${encodeURIComponent(runId)}/image`,
      imageFileName,
      mediaType,
      model: agentResult.metadata?.model || model,
      provider: agentResult.metadata?.provider || "imagent",
      costUsd: Number(agentResult.metadata?.cost_usd || 0),
      latencyMs: Number(agentResult.metadata?.latency_ms || Math.round((performance.now() - started) * 1000) / 1000),
      agentId: agentResult.agent_id || agentResult.metadata?.agent_id || "image-agent",
      capability: agentResult.capability || "plan",
      candidateCount: Number(agentResult.candidate_count || agentResult.metadata?.candidate_count || 0),
      roundCount: Number(agentResult.round_count || 0),
      selectedCandidateIndex: Number(
        agentResult.selected_candidate_index ?? agentResult.metadata?.selected_candidate_index ?? 0
      ),
      traceUrl: traceFileName ? `/api/playground/runs/${encodeURIComponent(runId)}/trace` : undefined
    });
  } catch (error) {
    // Log the detailed cause (Python stderr, filesystem paths, timeouts) on the
    // server only; never leak it to the client.
    console.error("Imagent generation failed:", error);
    return NextResponse.json({ error: "Imagent generation failed. Please try again." }, { status: 502 });
  } finally {
    releaseGenerationSlot();
    // Best-effort cap on data/agent-runs/ growth; never blocks the response path.
    void pruneRunDirectories().catch(() => {});
  }
}
