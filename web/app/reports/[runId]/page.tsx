import { ExternalLink, GitMerge, GitPullRequestClosed, Minus } from "lucide-react";
import { notFound } from "next/navigation";
import { getReport, listReports, toLeaderboardEntry } from "@/lib/reports";

type PageProps = {
  params: Promise<{ runId: string }>;
};

export async function generateStaticParams() {
  const reports = await listReports();
  return reports.map((report) => ({ runId: report.run_id }));
}

export default async function ReportPage({ params }: PageProps) {
  const { runId } = await params;
  const report = await getReport(runId);
  if (!report) {
    notFound();
  }
  const entry = toLeaderboardEntry(report);

  return (
    <section className="report-page">
      <div className="report-hero">
        <div className="report-owner">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={entry.contributor.avatar_url || ""} alt="" />
          <div>
            <h1>{entry.agentName}</h1>
            <p>{entry.repository}</p>
          </div>
        </div>
        <div className="report-score">
          <strong>{entry.score.toFixed(2)}</strong>
          <span className={entry.status}>{entry.status}</span>
        </div>
      </div>

      <div className="report-grid">
        <section className="report-panel pr-panel">
          <div>
            <h2>Pull Request</h2>
            <p>{entry.pullRequest.number === null ? entry.pullRequest.title : `#${entry.pullRequest.number} ${entry.pullRequest.title}`}</p>
          </div>
          <span className={`pr-state ${entry.pullRequest.state}`}>
            {entry.pullRequest.state === "merged" ? (
              <GitMerge size={15} />
            ) : entry.pullRequest.state === "unknown" ? (
              <Minus size={15} />
            ) : (
              <GitPullRequestClosed size={15} />
            )}
            {entry.pullRequest.state}
          </span>
          {entry.pullRequest.source === "derived" ? <small>GitHub pull request metadata was not attached to this report.</small> : null}
          {entry.pullRequest.html_url ? (
            <a className="external-link" href={entry.pullRequest.html_url}>
              GitHub <ExternalLink size={14} />
            </a>
          ) : null}
        </section>

        <Metric label="Latency p95" value={`${entry.latencyP95Ms.toFixed(1)} ms`} />
        <Metric label="Cost" value={`$${entry.costUsd.toFixed(6)}`} />
        <Metric label="Cases" value={String(report.metrics.case_count)} />
        <Metric label="Benchmark" value={report.benchmark_version} />
        <Metric label="Image model" value={entry.generationModel || "unknown"} />
        <Metric label="Commit" value={shortSha(report.commit_sha)} />
      </div>

      {report.policy.reasons.length > 0 ? (
        <section className="report-panel">
          <h2>Policy</h2>
          <ul className="policy-list">
            {report.policy.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="report-panel">
        <h2>Case Results</h2>
        <div className="case-list">
          {report.cases.map((item) => (
            <article className="case-row" key={item.id}>
              <div>
                <h3>{item.id}</h3>
                <p>{item.prompt}</p>
              </div>
              <div className="case-score">
                <span>{item.score.toFixed(2)}</span>
                <small className={item.status}>{item.status}</small>
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="report-panel metric-tile">
      <span>{value}</span>
      <small>{label}</small>
    </div>
  );
}

function shortSha(value: string) {
  return value.length > 12 ? value.slice(0, 12) : value;
}
