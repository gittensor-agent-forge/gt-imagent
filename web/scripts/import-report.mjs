import { copyFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";

const source = process.argv[2];
if (!source) {
  console.error("usage: npm run import-report -- /path/to/benchmark-report.json");
  process.exit(2);
}

const raw = await readFile(source, "utf8");
const report = JSON.parse(raw);
if (!isValidBenchmarkReport(report)) {
  console.error("input is not an imagent benchmark report");
  process.exit(1);
}

const destinationDir = path.join(process.cwd(), "data", "reports");
await mkdir(destinationDir, { recursive: true });
const destination = path.join(destinationDir, `${safeIdentifier(report.run_id)}.json`);
await copyFile(source, destination);
console.log(destination);

function isValidBenchmarkReport(value) {
  return Boolean(
    isRecord(value) &&
    value.schema_version === "1.0" &&
    safeIdentifier(value.run_id) &&
    nonEmptyString(value.repository) &&
    nonEmptyString(value.commit_sha) &&
    nonEmptyString(value.benchmark_version) &&
    nonEmptyString(value.dataset_version) &&
    (value.status === "pass" || value.status === "fail") &&
    finiteNumber(value.overall_score) !== null &&
    finiteNumber(value.execution_time_ms) !== null &&
    nonEmptyString(value.started_at) &&
    nonEmptyString(value.completed_at) &&
    isValidMetrics(value.metrics) &&
    Array.isArray(value.cases) &&
    Array.isArray(value.artifacts) &&
    Array.isArray(value.logs) &&
    isRecord(value.configuration) &&
    isRecord(value.policy)
  );
}

function isValidMetrics(value) {
  return Boolean(
    isRecord(value) &&
    finiteNumber(value.overall_score) !== null &&
    integerNumber(value.case_count) !== null &&
    integerNumber(value.failed_case_count) !== null &&
    finiteNumber(value.latency_p95_ms) !== null &&
    finiteNumber(value.cost_usd) !== null &&
    isRecord(value.latency_ms) &&
    finiteNumber(value.latency_ms.min) !== null &&
    finiteNumber(value.latency_ms.max) !== null &&
    finiteNumber(value.latency_ms.mean) !== null
  );
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function safeIdentifier(value) {
  const text = nonEmptyString(value);
  return text && /^[A-Za-z0-9._-]+$/.test(text) ? text : null;
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function integerNumber(value) {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}
