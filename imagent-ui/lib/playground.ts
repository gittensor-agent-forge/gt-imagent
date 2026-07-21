import { execFile } from "node:child_process";
import type { Dirent } from "node:fs";
import { promises as fs } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const RUN_MANIFEST_FILE = "result.json";

export { IMAGENT_GENERATION_MODEL_ID as DEFAULT_GENERATION_MODEL } from "./models";

// Server-side allow-lists for generation inputs. These mirror the choices the
// client offers and must never be inferred from the request body.
export const QUALITY_OPTIONS = ["auto", "low", "medium", "high"] as const;
export const BACKGROUND_OPTIONS = ["auto", "transparent", "opaque"] as const;

// Keep the newest N run directories under data/agent-runs/; older ones are pruned.
const MAX_RETAINED_RUN_DIRECTORIES = 200;

export type PlaygroundRuntimeStatus = {
  ready: boolean;
  hasServerApiKey: boolean;
  issues: string[];
};

export type RunManifest = {
  runId: string;
  imageFileName: string;
  imageMediaType: string;
  traceFileName?: string | null;
};

export type ResolvedPlaygroundRuntime = PlaygroundRuntimeStatus & {
  outputRoot: string;
  pythonBin: string;
  repositoryPath: string;
  scriptPath: string;
};

export function resolvePlaygroundEnvironment() {
  const configuredServerApiKey = String(process.env.OPENROUTER_API_KEY || "").trim();
  return {
    allowServerKeyFallback: envFlagEnabled(process.env.IMAGENT_UI_ENABLE_SERVER_KEY_FALLBACK),
    configuredServerApiKey,
    outputRoot: path.join(process.cwd(), "data", "agent-runs"),
    pythonBin: String(process.env.IMAGENT_PYTHON_BIN || "python3").trim() || "python3",
    repositoryPath: String(process.env.IMAGENT_REPOSITORY_PATH || path.resolve(process.cwd(), "..", "imagent")).trim(),
    scriptPath: path.join(process.cwd(), "scripts", "run_imagent_agent.py")
  };
}

export async function getResolvedPlaygroundRuntime(): Promise<ResolvedPlaygroundRuntime> {
  const environment = resolvePlaygroundEnvironment();
  const issues: string[] = [];

  if (!(await isDirectory(environment.repositoryPath))) {
    issues.push("The Imagent repository is not available to the UI server.");
  }
  if (!(await isFile(environment.scriptPath))) {
    issues.push("The UI runner script is missing on the server.");
  }
  if (!(await supportsPython(environment.pythonBin))) {
    issues.push("Python is not available to the UI server.");
  }

  return {
    ready: issues.length === 0,
    hasServerApiKey: environment.allowServerKeyFallback && Boolean(environment.configuredServerApiKey),
    outputRoot: environment.outputRoot,
    pythonBin: environment.pythonBin,
    repositoryPath: environment.repositoryPath,
    scriptPath: environment.scriptPath,
    issues
  };
}

export async function getPlaygroundRuntimeStatus(): Promise<PlaygroundRuntimeStatus> {
  const runtime = await getResolvedPlaygroundRuntime();
  return {
    ready: runtime.ready,
    hasServerApiKey: runtime.hasServerApiKey,
    issues: runtime.issues
  };
}

export function resolveRunDirectory(runId: string) {
  const safeRunId = validateRunId(runId);
  if (!safeRunId) {
    throw new Error("Invalid run ID.");
  }
  return path.join(resolvePlaygroundEnvironment().outputRoot, safeRunId);
}

export async function loadRunManifest(runId: string): Promise<RunManifest | null> {
  const safeRunId = validateRunId(runId);
  if (!safeRunId) {
    return null;
  }

  const manifestPath = path.join(resolveRunDirectory(safeRunId), RUN_MANIFEST_FILE);
  try {
    const raw = await fs.readFile(manifestPath, "utf8");
    const manifest = JSON.parse(raw) as RunManifest;
    if (
      typeof manifest.runId !== "string" ||
      manifest.runId !== safeRunId ||
      !isSafeArtifactFileName(manifest.imageFileName) ||
      typeof manifest.imageMediaType !== "string" ||
      (manifest.traceFileName != null && !isSafeArtifactFileName(manifest.traceFileName))
    ) {
      return null;
    }
    return manifest;
  } catch {
    return null;
  }
}

export async function writeRunManifest(runId: string, manifest: RunManifest) {
  const manifestPath = path.join(resolveRunDirectory(runId), RUN_MANIFEST_FILE);
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
}

export function validateRunId(value: string) {
  if (!/^[A-Za-z0-9._-]+$/.test(value)) {
    return null;
  }
  // Reject "." / ".." / any all-dots name so a run ID can never resolve to a
  // parent or the current directory even though "." is in the charset.
  if (/^\.+$/.test(value)) {
    return null;
  }
  return value;
}

/**
 * Content type used when serving a stored artifact inline. SVG is deliberately
 * downgraded to a neutral binary type so a malicious stored svg cannot execute
 * script in our origin, while real raster images still render inline.
 */
export function safeInlineContentType(mediaType: string, fileName: string) {
  const extension = path.extname(fileName).toLowerCase();
  if (extension === ".svg" || mediaType === "image/svg+xml") {
    return "application/octet-stream";
  }
  return mediaType;
}

/**
 * Best-effort cap on data/agent-runs/ growth: keep the newest
 * MAX_RETAINED_RUN_DIRECTORIES run directories (by mtime) and remove the rest.
 * Failures are swallowed so pruning never breaks a generation.
 */
export async function pruneRunDirectories(keep: number = MAX_RETAINED_RUN_DIRECTORIES) {
  const root = resolvePlaygroundEnvironment().outputRoot;
  let entries: Dirent[];
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    return;
  }

  const runDirs = entries.filter((entry) => entry.isDirectory() && validateRunId(entry.name));
  if (runDirs.length <= keep) {
    return;
  }

  const withMtime = await Promise.all(
    runDirs.map(async (entry) => {
      const fullPath = path.join(root, entry.name);
      try {
        const stat = await fs.stat(fullPath);
        return { fullPath, mtimeMs: stat.mtimeMs };
      } catch {
        return { fullPath, mtimeMs: 0 };
      }
    })
  );

  withMtime.sort((left, right) => right.mtimeMs - left.mtimeMs);
  const stale = withMtime.slice(keep);
  await Promise.all(
    stale.map((entry) => fs.rm(entry.fullPath, { recursive: true, force: true }).catch(() => {}))
  );
}

export function contentTypeForImage(imagePath: string) {
  const extension = path.extname(imagePath).toLowerCase();
  if (extension === ".jpg" || extension === ".jpeg") {
    return "image/jpeg";
  }
  if (extension === ".webp") {
    return "image/webp";
  }
  if (extension === ".gif") {
    return "image/gif";
  }
  if (extension === ".svg") {
    return "image/svg+xml";
  }
  return "image/png";
}

async function isDirectory(filePath: string) {
  try {
    return (await fs.stat(filePath)).isDirectory();
  } catch {
    return false;
  }
}

async function isFile(filePath: string) {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch {
    return false;
  }
}

async function supportsPython(pythonBin: string) {
  try {
    await execFileAsync(pythonBin, ["--version"], { maxBuffer: 64 * 1024 });
    return true;
  } catch {
    return false;
  }
}

function isSafeArtifactFileName(fileName: string) {
  return /^[A-Za-z0-9._-]+$/.test(fileName);
}

function envFlagEnabled(value: string | undefined) {
  return /^(1|true|yes|on)$/i.test(String(value || "").trim());
}
