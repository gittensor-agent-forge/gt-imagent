import { promises as fs } from "fs";
import path from "path";
import { cache } from "react";

export type Artifact = {
  type: string;
  path: string;
  sha256: string;
  media_type: string | null;
};

export type CaseResult = {
  id: string;
  numeric_id: number;
  prompt: string;
  capability: string;
  status: "pass" | "fail" | "error";
  score: number;
  latency_ms: number;
  cost_usd: number;
  checks: Array<Record<string, unknown>>;
  artifacts: Artifact[];
  dimensions?: Record<string, unknown> | null;
  judge?: Record<string, unknown> | null;
  error?: string | null;
};

export type RankingMetadata = {
  baseline_score?: number | null;
  baseline_commit?: string | null;
  candidate_score?: number | null;
  delta?: number | null;
  label?: string | null;
  merge_eligible?: boolean | null;
};

export type BenchmarkReport = {
  schema_version: "1.0";
  run_id: string;
  repository: string;
  commit_sha: string;
  pull_request?: PullRequestMetadata | null;
  contributor?: ContributorMetadata | null;
  benchmark_version: string;
  dataset_version: string;
  status: "pass" | "fail";
  overall_score: number;
  metrics: {
    overall_score: number;
    case_count: number;
    failed_case_count: number;
    latency_ms: {
      min: number;
      max: number;
      mean: number;
    };
    latency_p95_ms: number;
    cost_usd: number;
  };
  cases: CaseResult[];
  ranking?: RankingMetadata | null;
  artifacts: Artifact[];
  logs: Artifact[];
  configuration: {
    agent_manifest: {
      id?: string;
      name?: string;
      version?: string;
      entrypoint?: string;
    };
    agent_config: Record<string, unknown>;
    execution: Record<string, unknown>;
  };
  policy: {
    passed: boolean;
    reasons: string[];
    thresholds: Record<string, unknown>;
  };
  started_at: string;
  completed_at: string;
  execution_time_ms: number;
};

export type ContributorMetadata = {
  login: string;
  name?: string | null;
  avatar_url?: string | null;
  html_url?: string | null;
};

export type PullRequestMetadata = {
  number: number | null;
  title: string;
  state: "open" | "closed" | "merged" | "unknown";
  html_url?: string | null;
  merged_at?: string | null;
  closed_at?: string | null;
  source?: "report" | "derived";
};

export type LeaderboardEntry = {
  rank: number;
  runId: string;
  agentName: string;
  repository: string;
  commitSha: string;
  score: number;
  status: BenchmarkReport["status"];
  latencyP95Ms: number;
  costUsd: number;
  benchmarkVersion: string;
  completedAt: string;
  dimensions: Array<{
    name: string;
    score: number;
  }>;
  improvement: {
    baselineScore: number | null;
    baselineCommit: string | null;
    candidateScore: number;
    delta: number | null;
    label: string;
    mergeEligible: boolean;
    source: "ranking" | "history" | "none";
  };
  generationModel: string | null;
  judgeModel: string | null;
  contributor: (Required<Pick<ContributorMetadata, "login">> & Omit<ContributorMetadata, "login">) & {
    source: "report" | "derived";
  };
  pullRequest: PullRequestMetadata;
};

const reportsDir = path.join(process.cwd(), "data", "reports");

// Memoized per server render pass so a single request (or the static build) that
// touches reports through getReport / listLeaderboardEntries / generateStaticParams
// reads and validates the report files at most once instead of re-parsing them each call.
export const listReports = cache(async function listReports(): Promise<BenchmarkReport[]> {
  await fs.mkdir(reportsDir, { recursive: true });
  const names = await fs.readdir(reportsDir);
  const reports = await Promise.all(
    names
      .filter((name) => name.endsWith(".json"))
      .map(async (name) => readReport(path.join(reportsDir, name)))
  );
  return reports
    .filter((report): report is BenchmarkReport => report !== null)
    .sort((left, right) => {
      if (right.overall_score !== left.overall_score) {
        return right.overall_score - left.overall_score;
      }
      return Date.parse(right.completed_at) - Date.parse(left.completed_at);
    });
});

export async function getReport(runId: string): Promise<BenchmarkReport | null> {
  const reports = await listReports();
  return reports.find((report) => report.run_id === runId) ?? null;
}

export async function listLeaderboardEntries(): Promise<LeaderboardEntry[]> {
  const reports = await listReports();
  return reports.map((report, index) => toLeaderboardEntry(report, index + 1));
}

export function toLeaderboardEntry(report: BenchmarkReport, rank = 1): LeaderboardEntry {
  const agentName = report.configuration.agent_manifest.name || report.configuration.agent_manifest.id || "Image Agent";
  const contributor = normalizeContributor(report);
  const pullRequest = normalizePullRequest(report);
  const improvement = normalizeImprovement(report);
  return {
    rank,
    runId: report.run_id,
    agentName,
    repository: report.repository,
    commitSha: report.commit_sha,
    score: report.overall_score,
    status: report.status,
    latencyP95Ms: report.metrics.latency_p95_ms,
    costUsd: report.metrics.cost_usd,
    benchmarkVersion: report.benchmark_version,
    completedAt: report.completed_at,
    dimensions: normalizeDimensions(report),
    improvement,
    generationModel: normalizeGenerationModel(report),
    judgeModel: normalizeJudgeModel(report),
    contributor,
    pullRequest
  };
}

async function readReport(filePath: string): Promise<BenchmarkReport | null> {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    return normalizeReport(JSON.parse(raw));
  } catch {
    return null;
  }
}

function normalizeReport(value: unknown): BenchmarkReport | null {
  if (!isRecord(value) || value.schema_version !== "1.0") {
    return null;
  }

  const runId = safeIdentifier(value.run_id);
  const repository = nonEmptyString(value.repository);
  const commitSha = nonEmptyString(value.commit_sha);
  const benchmarkVersion = nonEmptyString(value.benchmark_version);
  const datasetVersion = nonEmptyString(value.dataset_version);
  const status = isBenchmarkStatus(value.status) ? value.status : null;
  const overallScore = finiteNumber(value.overall_score);
  const metrics = normalizeMetrics(value.metrics);
  const cases = normalizeCaseResults(value.cases);
  const artifacts = normalizeArtifacts(value.artifacts);
  const logs = normalizeArtifacts(value.logs);
  const configuration = normalizeConfiguration(value.configuration);
  const policy = normalizePolicy(value.policy);
  const startedAt = nonEmptyString(value.started_at);
  const completedAt = nonEmptyString(value.completed_at);
  const executionTimeMs = finiteNumber(value.execution_time_ms);

  if (
    !runId ||
    !repository ||
    !commitSha ||
    !benchmarkVersion ||
    !datasetVersion ||
    !status ||
    overallScore === null ||
    !metrics ||
    !cases ||
    !artifacts ||
    !logs ||
    !configuration ||
    !policy ||
    !startedAt ||
    !completedAt ||
    executionTimeMs === null
  ) {
    return null;
  }

  return {
    schema_version: "1.0",
    run_id: runId,
    repository,
    commit_sha: commitSha,
    pull_request: normalizeReportPullRequest(value.pull_request),
    contributor: normalizeReportContributor(value.contributor),
    benchmark_version: benchmarkVersion,
    dataset_version: datasetVersion,
    status,
    overall_score: overallScore,
    metrics,
    cases,
    ranking: normalizeRanking(value.ranking),
    artifacts,
    logs,
    configuration,
    policy,
    started_at: startedAt,
    completed_at: completedAt,
    execution_time_ms: executionTimeMs
  };
}

function normalizeMetrics(value: unknown): BenchmarkReport["metrics"] | null {
  if (!isRecord(value)) {
    return null;
  }
  const overallScore = finiteNumber(value.overall_score);
  const caseCount = integerNumber(value.case_count);
  const failedCaseCount = integerNumber(value.failed_case_count);
  const latencyP95Ms = finiteNumber(value.latency_p95_ms);
  const costUsd = finiteNumber(value.cost_usd);
  const latency = normalizeLatencyMetrics(value.latency_ms);

  if (
    overallScore === null ||
    caseCount === null ||
    failedCaseCount === null ||
    latencyP95Ms === null ||
    costUsd === null ||
    !latency
  ) {
    return null;
  }

  return {
    overall_score: overallScore,
    case_count: caseCount,
    failed_case_count: failedCaseCount,
    latency_ms: latency,
    latency_p95_ms: latencyP95Ms,
    cost_usd: costUsd
  };
}

function normalizeLatencyMetrics(value: unknown): BenchmarkReport["metrics"]["latency_ms"] | null {
  if (!isRecord(value)) {
    return null;
  }
  const min = finiteNumber(value.min);
  const max = finiteNumber(value.max);
  const mean = finiteNumber(value.mean);
  if (min === null || max === null || mean === null) {
    return null;
  }
  return { min, max, mean };
}

function normalizeCaseResults(value: unknown): CaseResult[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const cases: CaseResult[] = [];
  for (const item of value) {
    const parsed = normalizeCaseResult(item);
    if (!parsed) {
      return null;
    }
    cases.push(parsed);
  }
  return cases;
}

function normalizeCaseResult(value: unknown): CaseResult | null {
  if (!isRecord(value)) {
    return null;
  }
  const id = nonEmptyString(value.id);
  const prompt = nonEmptyString(value.prompt);
  const capability = nonEmptyString(value.capability);
  const status = isCaseStatus(value.status) ? value.status : null;
  const score = finiteNumber(value.score);
  const latencyMs = finiteNumber(value.latency_ms);
  const costUsd = finiteNumber(value.cost_usd);
  const checks = Array.isArray(value.checks) ? value.checks.filter(isRecord) : null;
  const artifacts = normalizeArtifacts(value.artifacts);

  if (!id || !prompt || !capability || !status || score === null || latencyMs === null || costUsd === null || !checks || !artifacts) {
    return null;
  }

  return {
    id,
    numeric_id: integerNumber(value.numeric_id) ?? 0,
    prompt,
    capability,
    status,
    score,
    latency_ms: latencyMs,
    cost_usd: costUsd,
    checks,
    artifacts,
    dimensions: isRecord(value.dimensions) ? value.dimensions : null,
    judge: isRecord(value.judge) ? value.judge : null,
    error: optionalString(value.error)
  };
}

function normalizeArtifacts(value: unknown): Artifact[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const artifacts: Artifact[] = [];
  for (const item of value) {
    const parsed = normalizeArtifact(item);
    if (!parsed) {
      return null;
    }
    artifacts.push(parsed);
  }
  return artifacts;
}

function normalizeArtifact(value: unknown): Artifact | null {
  if (!isRecord(value)) {
    return null;
  }
  const type = nonEmptyString(value.type);
  const artifactPath = nonEmptyString(value.path);
  const sha256 = nonEmptyString(value.sha256);
  if (!type || !artifactPath || !sha256) {
    return null;
  }
  return {
    type,
    path: artifactPath,
    sha256,
    media_type: optionalString(value.media_type)
  };
}

function normalizeConfiguration(value: unknown): BenchmarkReport["configuration"] | null {
  if (!isRecord(value) || !isRecord(value.agent_manifest) || !isRecord(value.agent_config) || !isRecord(value.execution)) {
    return null;
  }
  return {
    agent_manifest: {
      id: optionalString(value.agent_manifest.id) ?? undefined,
      name: optionalString(value.agent_manifest.name) ?? undefined,
      version: optionalString(value.agent_manifest.version) ?? undefined,
      entrypoint: optionalString(value.agent_manifest.entrypoint) ?? undefined
    },
    agent_config: value.agent_config,
    execution: value.execution
  };
}

function normalizePolicy(value: unknown): BenchmarkReport["policy"] | null {
  if (!isRecord(value) || typeof value.passed !== "boolean" || !Array.isArray(value.reasons) || !isRecord(value.thresholds)) {
    return null;
  }
  const reasons = value.reasons.filter((reason): reason is string => typeof reason === "string");
  if (reasons.length !== value.reasons.length) {
    return null;
  }
  return {
    passed: value.passed,
    reasons,
    thresholds: value.thresholds
  };
}

function normalizeRanking(value: unknown): RankingMetadata | null {
  if (!isRecord(value)) {
    return null;
  }
  const candidateScore = finiteNumber(value.candidate_score);
  const label = nonEmptyString(value.label);
  if (candidateScore === null || !label || typeof value.merge_eligible !== "boolean") {
    return null;
  }
  return {
    baseline_score: finiteNumber(value.baseline_score),
    baseline_commit: optionalString(value.baseline_commit),
    candidate_score: candidateScore,
    delta: finiteNumber(value.delta),
    label,
    merge_eligible: value.merge_eligible
  };
}

function normalizeReportPullRequest(value: unknown): BenchmarkReport["pull_request"] {
  if (!isRecord(value)) {
    return null;
  }
  const number = integerNumber(value.number);
  const title = nonEmptyString(value.title);
  const state = isReportPullRequestState(value.state) ? value.state : null;
  if (number === null || !title || !state) {
    return null;
  }
  return {
    number,
    title,
    state,
    html_url: optionalString(value.html_url),
    merged_at: optionalString(value.merged_at),
    closed_at: optionalString(value.closed_at)
  };
}

function normalizeReportContributor(value: unknown): BenchmarkReport["contributor"] {
  if (!isRecord(value)) {
    return null;
  }
  const login = nonEmptyString(value.login);
  if (!login) {
    return null;
  }
  return {
    login,
    name: optionalString(value.name),
    avatar_url: optionalString(value.avatar_url),
    html_url: optionalString(value.html_url)
  };
}

function normalizeContributor(report: BenchmarkReport): LeaderboardEntry["contributor"] {
  if (report.contributor?.login) {
    return {
      login: report.contributor.login,
      name: report.contributor.name ?? report.contributor.login,
      avatar_url: report.contributor.avatar_url ?? avatarFor(report.contributor.login),
      html_url: report.contributor.html_url ?? `https://github.com/${report.contributor.login}`,
      source: "report"
    };
  }

  const fallbackLogin = repositoryOwner(report.repository) || "local-miner";
  return {
    login: fallbackLogin,
    name: fallbackLogin,
    avatar_url: avatarFor(fallbackLogin),
    html_url: `https://github.com/${fallbackLogin}`,
    source: "derived"
  };
}

function normalizePullRequest(report: BenchmarkReport): PullRequestMetadata {
  if (report.pull_request?.number) {
    return {
      number: report.pull_request.number,
      title: report.pull_request.title || `Benchmark run ${report.run_id}`,
      state: report.pull_request.state || "unknown",
      html_url: report.pull_request.html_url ?? null,
      merged_at: report.pull_request.merged_at ?? null,
      closed_at: report.pull_request.closed_at ?? null,
      source: "report"
    };
  }

  return {
    number: null,
    title: "Imported report metadata unavailable",
    state: "unknown",
    html_url: null,
    merged_at: null,
    closed_at: null,
    source: "derived"
  };
}

function normalizeImprovement(report: BenchmarkReport): LeaderboardEntry["improvement"] {
  const ranking = report.ranking ?? null;
  const candidateScore = finiteNumber(ranking?.candidate_score) ?? report.overall_score;
  const baselineScore = finiteNumber(ranking?.baseline_score) ?? null;
  const delta = finiteNumber(ranking?.delta) ?? (baselineScore === null ? null : candidateScore - baselineScore);
  const label = normalizeImprovementLabel(ranking?.label, delta, baselineScore);
  const mergeEligible = typeof ranking?.merge_eligible === "boolean"
    ? ranking.merge_eligible
    : false;

  return {
    baselineScore,
    baselineCommit: ranking?.baseline_commit ?? null,
    candidateScore,
    delta,
    label,
    mergeEligible,
    source: ranking ? "ranking" : "none"
  };
}

function normalizeImprovementLabel(label: unknown, delta: number | null, baselineScore: number | null) {
  if (typeof label === "string" && label.trim()) {
    return label.trim();
  }
  if (baselineScore === null || delta === null) {
    return "baseline-unavailable";
  }
  if (delta < 0) {
    return "score-regression";
  }
  if (delta >= 10) {
    return "improvement-major";
  }
  if (delta >= 5) {
    return "improvement-strong";
  }
  if (delta > 0) {
    return "improvement-minor";
  }
  return "unchanged";
}

function normalizeDimensions(report: BenchmarkReport): LeaderboardEntry["dimensions"] {
  const totals = new Map<string, { count: number; total: number }>();

  for (const item of report.cases) {
    if (!item.dimensions || Array.isArray(item.dimensions)) {
      continue;
    }
    Object.entries(item.dimensions).forEach(([name, value]) => {
      const score = finiteNumber(value);
      if (score === null) {
        return;
      }
      const existing = totals.get(name) ?? { count: 0, total: 0 };
      existing.count += 1;
      existing.total += score;
      totals.set(name, existing);
    });
  }

  return Array.from(totals.entries())
    .map(([name, value]) => ({
      name,
      score: value.count > 0 ? value.total / value.count : 0
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

function normalizeJudgeModel(report: BenchmarkReport) {
  for (const item of report.cases) {
    const model = stringFromRecord(item.judge, "model") ?? stringFromRecord(item.judge, "provider");
    if (model) {
      return model;
    }
  }

  const imageJudge = report.configuration.agent_config?.evaluation;
  if (isRecord(imageJudge)) {
    const nested = imageJudge.image_judge;
    if (isRecord(nested)) {
      return stringFromRecord(nested, "model") ?? stringFromRecord(nested, "provider");
    }
  }

  return null;
}

function normalizeGenerationModel(report: BenchmarkReport) {
  const agentConfig = report.configuration.agent_config;
  if (!isRecord(agentConfig)) {
    return null;
  }

  const directModel = stringFromRecord(agentConfig, "model");
  if (directModel) {
    return directModel;
  }

  const nestedAgent = agentConfig.agent;
  if (!isRecord(nestedAgent)) {
    return null;
  }

  const imageBackend = nestedAgent.image_backend;
  if (!isRecord(imageBackend)) {
    return null;
  }

  return stringFromRecord(imageBackend, "model") ?? stringFromRecord(imageBackend, "provider");
}

function finiteNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function integerNumber(value: unknown) {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

function nonEmptyString(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function safeIdentifier(value: unknown) {
  const text = nonEmptyString(value);
  return text && /^[A-Za-z0-9._-]+$/.test(text) ? text : null;
}

function optionalString(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function isBenchmarkStatus(value: unknown): value is BenchmarkReport["status"] {
  return value === "pass" || value === "fail";
}

function isCaseStatus(value: unknown): value is CaseResult["status"] {
  return value === "pass" || value === "fail" || value === "error";
}

function isReportPullRequestState(value: unknown): value is "open" | "closed" | "merged" {
  return value === "open" || value === "closed" || value === "merged";
}

function stringFromRecord(value: unknown, key: string) {
  if (!isRecord(value)) {
    return null;
  }
  const candidate = value[key];
  return typeof candidate === "string" && candidate.trim() ? candidate.trim() : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function avatarFor(login: string) {
  const initials = login
    .split(/[-_\s]+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "IA";
  const colors = ["#04183b", "#0358bc", "#0478e8", "#0aa6d8", "#1dd9f5"];
  const fill = colors[stableNumber(login) % colors.length];
  const svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">',
    `<rect width="96" height="96" rx="24" fill="${fill}"/>`,
    `<text x="48" y="56" text-anchor="middle" font-family="JetBrains Mono, Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#fff">${escapeSvg(initials)}</text>`,
    "</svg>"
  ].join("");
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function escapeSvg(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function stableNumber(value: string) {
  let hash = 0;
  for (const character of value) {
    hash = (hash * 31 + character.charCodeAt(0)) % 9000;
  }
  return hash + 100;
}

function repositoryOwner(repository: string) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
    return null;
  }
  return repository.split("/")[0];
}
