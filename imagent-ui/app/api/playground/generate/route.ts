import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";
import {
  contentTypeForImage,
  DEFAULT_GENERATION_MODEL,
  getResolvedPlaygroundRuntime,
  resolveRunDirectory,
  validateRunId,
  writeRunManifest
} from "@/lib/playground";
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

export async function POST(request: Request) {
  const started = performance.now();
  const body = (await request.json()) as GenerateRequest;
  const publicSiteUrl = resolvePublicSiteUrl();
  const prompt = String(body.prompt || "").trim();
  const model = DEFAULT_GENERATION_MODEL;
  const quality = String(body.quality || "auto").trim();
  const background = String(body.background || "auto").trim();
  const runtime = await getResolvedPlaygroundRuntime();
  const apiKey = String(body.apiKey || (runtime.hasServerApiKey ? process.env.OPENROUTER_API_KEY : "") || "").trim();

  if (!prompt) {
    return NextResponse.json({ error: "Prompt is required." }, { status: 400 });
  }
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

  const runId = `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  if (!validateRunId(runId)) {
    return NextResponse.json({ error: "Failed to allocate a valid run ID." }, { status: 500 });
  }
  const outputDir = resolveRunDirectory(runId);
  const requestPath = path.join(outputDir, "request.json");

  try {
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
      maxBuffer: 10 * 1024 * 1024
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
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Imagent generation failed."
      },
      { status: 502 }
    );
  }
}
