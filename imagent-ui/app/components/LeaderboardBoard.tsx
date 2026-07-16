"use client";

import {
  Activity,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Crown,
  Eye,
  GitMerge,
  GitPullRequest,
  GitPullRequestArrow,
  History,
  Hourglass,
  List,
  Minus,
  MoreHorizontal,
  Search,
  Timer,
  TrendingDown,
  TrendingUp,
  WalletCards,
  X,
  XCircle
} from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { LeaderboardEntry } from "@/lib/reports";

type HistoryFilter = "all" | "merged" | "closed" | "eligible" | "failed";
type PullRequestStatus = {
  icon: ReactNode;
  label: string;
  tone: "merged" | "closed" | "unknown";
};
type BenchmarkStatus = {
  label: string;
  tone: "passed" | "failed";
};
type EligibilityStatus = {
  label: string;
  tone: "eligible" | "ineligible";
};

const HISTORY_PAGE_SIZES = [4, 8, 12] as const;

const historyFilters: Array<{ id: HistoryFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "merged", label: "Merged" },
  { id: "closed", label: "Closed" },
  { id: "eligible", label: "Eligible" },
  { id: "failed", label: "Benchmark failed" }
];

export function LeaderboardBoard({ entries }: { entries: LeaderboardEntry[] }) {
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>("all");
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState<number>(HISTORY_PAGE_SIZES[0]);
  const [query, setQuery] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<LeaderboardEntry | null>(null);
  const [mounted, setMounted] = useState(false);
  // `now` stays null until the client mounts. Seeding it with Date.now() during
  // render made the server bake one clock reading into the SSR HTML while
  // hydration computed another, so recent "x ago" timestamps mismatched and
  // React discarded and re-rendered the tree. Relative time is now purely
  // client-driven, starting on mount.
  const [now, setNow] = useState<number | null>(null);
  const modalTriggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const king = useMemo(() => getCurrentKing(entries), [entries]);
  const filteredHistoryEntries = useMemo(
    () => buildHistory(entries, historyFilter, query),
    [entries, historyFilter, query]
  );
  const historyPageCount = Math.max(1, Math.ceil(filteredHistoryEntries.length / historyPageSize));
  const activeHistoryPage = Math.min(historyPage, historyPageCount);
  const historyEntries = useMemo(() => {
    const start = (activeHistoryPage - 1) * historyPageSize;
    return filteredHistoryEntries.slice(start, start + historyPageSize);
  }, [activeHistoryPage, filteredHistoryEntries, historyPageSize]);
  const openEntryDetails = useCallback((entry: LeaderboardEntry, trigger: HTMLElement) => {
    modalTriggerRef.current = trigger;
    setSelectedEntry(entry);
  }, []);
  const closeEntryDetails = useCallback(() => {
    setSelectedEntry(null);
  }, []);

  return (
    <>
      <section className="leaderboard-live-shell leaderboard-state-shell" aria-label="PR benchmark history">
        <h1 className="leaderboard-page-title">PR Benchmark History</h1>

        <div className="leaderboard-state-priority">
          <CandidateQueue />
          <KingCard entry={king} onOpenDetails={openEntryDetails} />
        </div>

        <HistoryPanel
          entries={historyEntries}
          filter={historyFilter}
          now={now}
          onFilterChange={(nextFilter) => {
            setHistoryFilter(nextFilter);
            setHistoryPage(1);
          }}
          onOpenDetails={openEntryDetails}
          onPageChange={setHistoryPage}
          onPageSizeChange={(nextPageSize) => {
            setHistoryPageSize(nextPageSize);
            setHistoryPage(1);
          }}
          onQueryChange={(nextQuery) => {
            setQuery(nextQuery);
            setHistoryPage(1);
          }}
          page={activeHistoryPage}
          pageCount={historyPageCount}
          pageSize={historyPageSize}
          query={query}
          totalEntries={filteredHistoryEntries.length}
        />
      </section>
      {mounted && selectedEntry ? (
        <PrDetailModal
          entry={selectedEntry}
          now={now}
          onClose={closeEntryDetails}
          trigger={modalTriggerRef.current}
        />
      ) : null}
    </>
  );
}

function KingCard({
  entry,
  onOpenDetails
}: {
  entry: LeaderboardEntry | null;
  onOpenDetails: (entry: LeaderboardEntry, trigger: HTMLElement) => void;
}) {
  if (!entry) {
    return (
      <section className="leaderboard-king-panel leaderboard-king-panel-empty">
        <div className="leaderboard-king-empty">
          <span><Crown size={24} /></span>
          <div>
            <strong>No King Yet</strong>
            <p>The first completed benchmark will set the current king.</p>
          </div>
        </div>
      </section>
    );
  }

  const prState = pullRequestStatus(entry);
  const benchmark = benchmarkStatus(entry);
  const eligibility = eligibilityStatus(entry);

  return (
    <section className="leaderboard-king-panel" aria-label="Current benchmark king">
      <div className="leaderboard-king-head">
        <span className="leaderboard-king-title"><Crown size={15} />King</span>
        <div className="leaderboard-king-head-actions">
          <span className={`leaderboard-king-state ${prState.tone}`}>
            {prState.icon}
            {prState.label}
          </span>
          <button
            aria-label="View current king details"
            className="leaderboard-king-report-icon"
            onClick={(event) => onOpenDetails(entry, event.currentTarget)}
            title="View PR details"
            type="button"
          >
            <Eye size={15} />
          </button>
        </div>
      </div>

      <div className="leaderboard-king-main">
        <div className="leaderboard-king-identity">
          <Avatar contributor={entry.contributor} className="king" />
          <div className="leaderboard-king-copy">
            <h2>{pullRequestLabel(entry)}</h2>
            <p className="leaderboard-king-pr-title" title={entry.pullRequest.title}>{entry.pullRequest.title}</p>
            <div className="leaderboard-king-meta">
              <span>@{entry.contributor.login}</span>
              <span className={`leaderboard-king-meta-label ${benchmark.tone}`}>{benchmark.label}</span>
              <span className={`leaderboard-king-meta-label ${eligibility.tone}`}>{eligibility.label}</span>
            </div>
          </div>
        </div>

        <div className="leaderboard-king-score">
          <span>Benchmark Score</span>
          <strong>{entry.score.toFixed(2)}</strong>
          <em className={`leaderboard-delta ${deltaTone(entry.improvement.delta)}`}>
            {deltaIcon(entry.improvement.delta)}
            {formatDelta(entry.improvement.delta)}
          </em>
        </div>
      </div>

      <div className="leaderboard-king-detail-grid">
        <KingDetailMetric icon={<Timer size={14} />} label="P95 latency" value={`${entry.latencyP95Ms.toFixed(0)} ms`} />
        <KingDetailMetric icon={<WalletCards size={14} />} label="Run cost" value={`$${entry.costUsd.toFixed(5)}`} />
        <KingDetailMetric icon={<Activity size={14} />} label="Benchmark" value={formatBenchmarkVersion(entry.benchmarkVersion)} />
      </div>

      <div className="leaderboard-king-model-grid">
        <KingModelDetail label="Generation Model" model={entry.generationModel} />
        <KingModelDetail label="Evaluation Model" model={entry.judgeModel} />
      </div>

      <div className="leaderboard-king-detail-section leaderboard-king-dimensions">
        <span>Benchmark Profile</span>
        {entry.dimensions.length ? (
          <div className="leaderboard-king-dimension-list">
            {entry.dimensions.slice(0, 5).map((dimension) => (
              <div className="leaderboard-king-dimension" key={dimension.name}>
                <div>
                  <span>{formatDimension(dimension.name)}</span>
                  <strong>{dimension.score.toFixed(0)}</strong>
                </div>
                <i><b style={{ width: scoreWidth(dimension.score) }} /></i>
              </div>
            ))}
          </div>
        ) : (
          <small>Dimension scores are unavailable for this report.</small>
        )}
      </div>

    </section>
  );
}

function CandidateQueue() {
  return (
    <section className="leaderboard-candidate-region" aria-label="Candidate PR queue">
      <section className="leaderboard-candidate-panel">
        <div className="leaderboard-candidate-head">
          <PanelHeader inlineValue icon={<GitPullRequestArrow size={15} />} title="Candidate Queue" value="Paused" />
        </div>

        <div className="leaderboard-candidate-empty">
          <div className="leaderboard-candidate-empty-copy">
            <span><Hourglass size={22} /></span>
            <div>
              <strong>Candidate intake is paused</strong>
              <p>Active pull request evaluations will appear here when the benchmark workflow resumes.</p>
            </div>
          </div>
        </div>
      </section>
    </section>
  );
}

function HistoryPanel({
  entries,
  filter,
  now,
  onFilterChange,
  onOpenDetails,
  onPageChange,
  onPageSizeChange,
  onQueryChange,
  page,
  pageCount,
  pageSize,
  query,
  totalEntries
}: {
  entries: LeaderboardEntry[];
  filter: HistoryFilter;
  now: number | null;
  onFilterChange: (filter: HistoryFilter) => void;
  onOpenDetails: (entry: LeaderboardEntry, trigger: HTMLElement) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onQueryChange: (query: string) => void;
  page: number;
  pageCount: number;
  pageSize: number;
  query: string;
  totalEntries: number;
}) {
  return (
    <section className="leaderboard-history-panel" aria-label="Merged and closed PR history">
      <div className="leaderboard-history-head">
        <PanelHeader inlineValue icon={<History size={15} />} title="Resolved PR History" value={String(totalEntries)} />
        <label className="leaderboard-history-search">
          <Search size={15} />
          <input
            aria-label="Search evaluated PR history"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search PR, agent, contributor"
          />
        </label>
      </div>

      <div className="leaderboard-history-filters" aria-label="History filters">
        {historyFilters.map((item) => (
          <button
            className={filter === item.id ? "active" : ""}
            key={item.id}
            type="button"
            aria-pressed={filter === item.id}
            onClick={() => onFilterChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="leaderboard-history-list custom-scrollbar">
        {entries.length ? entries.map((entry) => (
          <HistoryItem
            entry={entry}
            key={entry.runId}
            now={now}
            onOpenDetails={onOpenDetails}
          />
        )) : (
          <div className="leaderboard-history-empty">
            <History size={20} />
            <strong>No Resolved PRs</strong>
            <p>No merged or closed pull requests match this view.</p>
          </div>
        )}
      </div>
      <HistoryPagination
        currentPage={page}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
        pageCount={pageCount}
        pageSize={pageSize}
        totalEntries={totalEntries}
      />
    </section>
  );
}

function HistoryItem({
  entry,
  now,
  onOpenDetails
}: {
  entry: LeaderboardEntry;
  now: number | null;
  onOpenDetails: (entry: LeaderboardEntry, trigger: HTMLElement) => void;
}) {
  const prState = pullRequestStatus(entry);
  const benchmark = benchmarkStatus(entry);
  const eligibility = eligibilityStatus(entry);

  return (
    <button
      aria-label={`View details for ${pullRequestText(entry.pullRequest)}`}
      className="leaderboard-history-item"
      onClick={(event) => onOpenDetails(entry, event.currentTarget)}
      type="button"
    >
      <div className="leaderboard-history-identity" aria-hidden="true">
        <Avatar contributor={entry.contributor} className="history" />
        <span className={`leaderboard-history-marker state-${prState.tone}`}>{prState.icon}</span>
      </div>
      <div className="leaderboard-history-main">
        <div className="leaderboard-history-title">
          <strong>{pullRequestText(entry.pullRequest)}</strong>
          <span className={`leaderboard-history-result state-${prState.tone}`}>{prState.label}</span>
        </div>
        <p title={entry.pullRequest.title}>{entry.pullRequest.title}</p>
        <div className="leaderboard-history-meta">
          <span className={`leaderboard-history-disposition ${benchmark.tone}`}>{benchmark.label}</span>
          <span className={`leaderboard-history-disposition ${eligibility.tone}`}>{eligibility.label}</span>
          <span>@{entry.contributor.login}</span>
          <span>{formatRelativeTime(entry.completedAt, now)}</span>
          <span>{formatShortSha(entry.commitSha)}</span>
        </div>
      </div>
      <div className="leaderboard-history-score">
        <strong>{entry.score.toFixed(2)}</strong>
        <span className={`leaderboard-delta ${deltaTone(entry.improvement.delta)}`}>
          {deltaIcon(entry.improvement.delta)}
          {formatDelta(entry.improvement.delta)}
        </span>
      </div>
    </button>
  );
}

function PrDetailModal({
  entry,
  now,
  onClose,
  trigger
}: {
  entry: LeaderboardEntry;
  now: number | null;
  onClose: () => void;
  trigger: HTMLElement | null;
}) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const prState = pullRequestStatus(entry);
  const benchmark = benchmarkStatus(entry);
  const eligibility = eligibilityStatus(entry);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const focusTimer = window.setTimeout(() => {
      const firstFocusable = dialogRef.current?.querySelector<HTMLElement>("button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
      (firstFocusable || dialogRef.current)?.focus({ preventScroll: true });
    }, 0);

    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const dialog = dialogRef.current;
      const focusableElements = dialog ? getModalFocusableElements(dialog) : [];
      if (!focusableElements.length) {
        event.preventDefault();
        dialog?.focus({ preventScroll: true });
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;

      if (event.shiftKey && (!dialog?.contains(activeElement) || activeElement === firstElement)) {
        event.preventDefault();
        lastElement.focus({ preventScroll: true });
      } else if (!event.shiftKey && (!dialog?.contains(activeElement) || activeElement === lastElement)) {
        event.preventDefault();
        firstElement.focus({ preventScroll: true });
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      trigger?.focus({ preventScroll: true });
    };
  }, [onClose, trigger]);

  return createPortal(
    <div
      className="leaderboard-pr-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
      role="presentation"
    >
      <section
        aria-labelledby="leaderboard-pr-modal-title"
        aria-modal="true"
        className="leaderboard-pr-modal"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
          <header>
            <div className="leaderboard-pr-modal-title-group">
              <span className={`leaderboard-pr-modal-icon ${prState.tone}`}><GitPullRequest size={20} /></span>
              <div>
                <div className="leaderboard-pr-modal-kicker">
                  <span>{pullRequestText(entry.pullRequest)}</span>
                  <span className={prState.tone}>{prState.label}</span>
                  <span className={benchmark.tone}>{benchmark.label}</span>
                  <span className={eligibility.tone}>{eligibility.label}</span>
                </div>
                <h2 id="leaderboard-pr-modal-title">{entry.pullRequest.title}</h2>
              </div>
            </div>
            <button aria-label="Close PR details" className="leaderboard-pr-modal-close" onClick={onClose} type="button">
              <X size={17} />
            </button>
          </header>

          <div className="leaderboard-pr-modal-body custom-scrollbar">
            <section className="leaderboard-pr-modal-summary">
              <div className="leaderboard-pr-modal-contributor">
                <Avatar className="modal" contributor={entry.contributor} />
                <div>
                  <strong>@{entry.contributor.login}</strong>
                  <span>Benchmark completed {formatRelativeTime(entry.completedAt, now)}</span>
                </div>
              </div>
              <div className="leaderboard-pr-modal-score">
                <span>Benchmark Score</span>
                <strong>{entry.score.toFixed(2)}</strong>
                <em className={`leaderboard-delta ${deltaTone(entry.improvement.delta)}`}>
                  {deltaIcon(entry.improvement.delta)}
                  {formatDelta(entry.improvement.delta)}
                </em>
              </div>
            </section>

            <div className="leaderboard-pr-modal-metrics">
              <PrModalMetric icon={<Activity size={14} />} label="Benchmark" value={formatBenchmarkVersion(entry.benchmarkVersion)} />
              <PrModalMetric icon={<GitPullRequest size={14} />} label="Commit" value={formatShortSha(entry.commitSha)} />
              <PrModalMetric icon={<Timer size={14} />} label="P95 latency" value={`${entry.latencyP95Ms.toFixed(0)} ms`} />
              <PrModalMetric icon={<WalletCards size={14} />} label="Run cost" value={`$${entry.costUsd.toFixed(5)}`} />
              <PrModalMetric icon={<Activity size={14} />} label="Generation model" value={formatModelName(entry.generationModel)} />
              <PrModalMetric icon={<History size={14} />} label="Evaluation model" value={formatModelName(entry.judgeModel)} />
            </div>

            <section className="leaderboard-pr-modal-dimensions">
              <span>Dimension Scores</span>
              {entry.dimensions.length ? (
                <div>
                  {entry.dimensions.slice(0, 6).map((dimension) => (
                    <div className="leaderboard-pr-modal-dimension" key={dimension.name}>
                      <div>
                        <span>{formatDimension(dimension.name)}</span>
                        <strong>{dimension.score.toFixed(0)}</strong>
                      </div>
                      <i><b style={{ width: scoreWidth(dimension.score) }} /></i>
                    </div>
                  ))}
                </div>
              ) : <small>Dimension scores are unavailable for this benchmark.</small>}
            </section>
          </div>
      </section>
    </div>,
    document.body
  );
}

function PrModalMetric({
  icon,
  label,
  value
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="leaderboard-pr-modal-metric">
      <span>{icon}{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function getModalFocusableElements(container: HTMLElement) {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    )
  ).filter((element) => element.getClientRects().length > 0);
}

function HistoryPageSizeMenu({
  pageSize,
  onPageSizeChange
}: {
  pageSize: number;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const menuId = useId();
  const menuRef = useRef<HTMLDivElement | null>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const selectedIndex = Math.max(
    0,
    HISTORY_PAGE_SIZES.indexOf(pageSize as (typeof HISTORY_PAGE_SIZES)[number])
  );

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const closeOnOutsidePress = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("pointerdown", closeOnOutsidePress);
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePress);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  const focusOption = (index: number) => {
    optionRefs.current[index]?.focus();
  };

  const openFromTrigger = (direction: "first" | "last" | "selected") => {
    setIsOpen(true);

    window.requestAnimationFrame(() => {
      if (direction === "first") {
        focusOption(0);
        return;
      }

      if (direction === "last") {
        focusOption(HISTORY_PAGE_SIZES.length - 1);
        return;
      }

      focusOption(selectedIndex);
    });
  };

  const selectPageSize = (size: number) => {
    onPageSizeChange(size);
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  return (
    <div
      className={`leaderboard-history-page-size${isOpen ? " is-open" : ""}`}
      onBlur={() => {
        window.setTimeout(() => {
          if (!menuRef.current?.contains(document.activeElement)) {
            setIsOpen(false);
          }
        }, 0);
      }}
      ref={menuRef}
    >
      <span className="leaderboard-history-page-size-label">
        <List aria-hidden="true" size={13} />
        Per page
      </span>
      <div className="leaderboard-history-page-size-control">
        <button
          aria-controls={menuId}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-label={`Rows per history page: ${pageSize}`}
          className="leaderboard-history-page-size-trigger"
          onClick={() => setIsOpen((open) => !open)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              openFromTrigger("first");
            }

            if (event.key === "ArrowUp") {
              event.preventDefault();
              openFromTrigger("last");
            }
          }}
          ref={triggerRef}
          type="button"
        >
          <span>{pageSize} rows</span>
          <ChevronDown aria-hidden="true" size={13} />
        </button>
        {isOpen ? (
          <div className="leaderboard-history-page-size-menu" id={menuId} role="listbox" aria-label="Rows per history page">
            {HISTORY_PAGE_SIZES.map((size, index) => {
              const selected = size === pageSize;

              return (
                <button
                  aria-selected={selected}
                  className={selected ? "is-selected" : ""}
                  key={size}
                  onClick={() => selectPageSize(size)}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      focusOption((index + 1) % HISTORY_PAGE_SIZES.length);
                    }

                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      focusOption((index - 1 + HISTORY_PAGE_SIZES.length) % HISTORY_PAGE_SIZES.length);
                    }

                    if (event.key === "Home") {
                      event.preventDefault();
                      focusOption(0);
                    }

                    if (event.key === "End") {
                      event.preventDefault();
                      focusOption(HISTORY_PAGE_SIZES.length - 1);
                    }
                  }}
                  ref={(element) => {
                    optionRefs.current[index] = element;
                  }}
                  role="option"
                  type="button"
                >
                  <span>{size} rows</span>
                  {selected ? <Check aria-hidden="true" size={14} /> : null}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function HistoryPagination({
  currentPage,
  onPageChange,
  onPageSizeChange,
  pageCount,
  pageSize,
  totalEntries
}: {
  currentPage: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageCount: number;
  pageSize: number;
  totalEntries: number;
}) {
  if (!totalEntries) {
    return null;
  }

  const start = (currentPage - 1) * pageSize + 1;
  const end = Math.min(totalEntries, currentPage * pageSize);
  const pages = historyPageTokens(pageCount, currentPage);

  return (
    <footer className="leaderboard-history-pagination">
      <div className="leaderboard-history-pagination-summary">
        <p>
          Showing <strong>{start}-{end}</strong> of <strong>{totalEntries}</strong>
        </p>
        <HistoryPageSizeMenu pageSize={pageSize} onPageSizeChange={onPageSizeChange} />
      </div>
      {pageCount > 1 ? (
        <nav aria-label="Resolved PR history pages">
          <button
            aria-label="Previous history page"
            disabled={currentPage === 1}
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            title="Previous page"
            type="button"
          >
            <ChevronLeft size={15} />
          </button>
          {pages.map((token, index) => token === "ellipsis" ? (
            <span className="leaderboard-history-page-ellipsis" key={`ellipsis-${index}`} aria-hidden="true">
              <MoreHorizontal size={15} />
            </span>
          ) : (
            <button
              aria-current={token === currentPage ? "page" : undefined}
              className={token === currentPage ? "active" : ""}
              key={token}
              onClick={() => onPageChange(token)}
              type="button"
            >
              {token}
            </button>
          ))}
          <button
            aria-label="Next history page"
            disabled={currentPage === pageCount}
            onClick={() => onPageChange(Math.min(pageCount, currentPage + 1))}
            title="Next page"
            type="button"
          >
            <ChevronRight size={15} />
          </button>
        </nav>
      ) : null}
    </footer>
  );
}

function PanelHeader({
  icon,
  inlineValue = false,
  title,
  value
}: {
  icon: ReactNode;
  inlineValue?: boolean;
  title: string;
  value: string;
}) {
  return (
    <header className={`leaderboard-panel-head${inlineValue ? " leaderboard-panel-head--inline-value" : ""}`}>
      <span>{icon}{title}</span>
      <strong>{value}</strong>
    </header>
  );
}

function KingDetailMetric({
  icon,
  label,
  value
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="leaderboard-king-detail-metric">
      <span>{icon}{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function KingModelDetail({
  label,
  model
}: {
  label: string;
  model: string | null;
}) {
  const displayName = formatModelName(model);
  const sourceName = model || "Model metadata unavailable";

  return (
    <div className="leaderboard-king-model-cell">
      <span>{label}</span>
      <strong title={sourceName}>{displayName}</strong>
    </div>
  );
}

function Avatar({
  className = "",
  contributor
}: {
  className?: string;
  contributor: LeaderboardEntry["contributor"];
}) {
  const label = contributor.login.slice(0, 2).toUpperCase();
  const source = contributor.avatar_url || githubAvatarUrl(contributor.login);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const showImage = failedSource !== source;

  return (
    <span className={`leaderboard-avatar ${className}`.trim()} title={`GitHub profile for @${contributor.login}`}>
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={source} alt="" onError={() => setFailedSource(source)} />
      ) : label}
    </span>
  );
}

function githubAvatarUrl(login: string) {
  return `https://github.com/${encodeURIComponent(login)}.png?size=96`;
}

function buildHistory(
  entries: LeaderboardEntry[],
  filter: HistoryFilter,
  query: string
) {
  const normalizedQuery = query.trim().toLowerCase();

  return [...entries]
    .filter((entry) => {
      if (!isResolvedPullRequest(entry)) {
        return false;
      }

      const matchesFilter =
        filter === "all" ||
        (filter === "merged" && entry.pullRequest.state === "merged") ||
        (filter === "closed" && entry.pullRequest.state === "closed") ||
        (filter === "eligible" && isEligible(entry)) ||
        (filter === "failed" && entry.status === "fail");

      if (!matchesFilter) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const haystack = [
        entry.agentName,
        entry.benchmarkVersion,
        entry.commitSha,
        entry.contributor.login,
        entry.contributor.name,
        entry.generationModel,
        entry.improvement.label,
        entry.judgeModel,
        entry.pullRequest.number === null ? "" : String(entry.pullRequest.number),
        entry.pullRequest.title,
        entry.repository,
        entry.runId
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    })
    .sort((left, right) => Date.parse(right.completedAt) - Date.parse(left.completedAt));
}

function getCurrentKing(entries: LeaderboardEntry[]) {
  return mostRecent(
    entries.filter((entry) => entry.status === "pass" && entry.improvement.mergeEligible && entry.pullRequest.state === "merged")
  ) ?? mostRecent(
    entries.filter((entry) => entry.status === "pass" && entry.improvement.mergeEligible)
  ) ?? mostRecent(entries.filter((entry) => entry.status === "pass")) ?? mostRecent(entries);
}

function mostRecent(entries: LeaderboardEntry[]) {
  return [...entries].sort((left, right) => {
    const leftTimestamp = parseTimestamp(left.pullRequest.merged_at || left.completedAt) ?? 0;
    const rightTimestamp = parseTimestamp(right.pullRequest.merged_at || right.completedAt) ?? 0;
    return rightTimestamp - leftTimestamp;
  })[0] ?? null;
}

function isEligible(entry: LeaderboardEntry) {
  return entry.status === "pass" && entry.improvement.mergeEligible;
}

function isResolvedPullRequest(entry: LeaderboardEntry) {
  return entry.pullRequest.state === "merged" || entry.pullRequest.state === "closed";
}

function pullRequestStatus(entry: LeaderboardEntry): PullRequestStatus {
  if (entry.pullRequest.state === "merged") {
    return { icon: <GitMerge size={14} />, label: "Merged", tone: "merged" };
  }
  if (entry.pullRequest.state === "closed") {
    return { icon: <XCircle size={14} />, label: "Closed", tone: "closed" };
  }
  return { icon: <GitPullRequest size={14} />, label: "State unavailable", tone: "unknown" };
}

function benchmarkStatus(entry: LeaderboardEntry): BenchmarkStatus {
  if (entry.status === "pass") {
    return { label: "Benchmark passed", tone: "passed" };
  }
  return { label: "Benchmark failed", tone: "failed" };
}

function eligibilityStatus(entry: LeaderboardEntry): EligibilityStatus {
  if (isEligible(entry)) {
    return { label: "Eligible", tone: "eligible" };
  }
  return { label: "Not eligible", tone: "ineligible" };
}

function historyPageTokens(pageCount: number, currentPage: number): Array<number | "ellipsis"> {
  if (pageCount <= 5) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }

  const selectedPages = new Set([1, pageCount, currentPage - 1, currentPage, currentPage + 1]);
  const pages = Array.from(selectedPages)
    .filter((page) => page >= 1 && page <= pageCount)
    .sort((left, right) => left - right);
  const tokens: Array<number | "ellipsis"> = [];

  pages.forEach((page, index) => {
    const previous = pages[index - 1];
    if (previous && page - previous > 1) {
      tokens.push("ellipsis");
    }
    tokens.push(page);
  });

  return tokens;
}

function formatDelta(value: number | null) {
  if (value === null) {
    return "N/A";
  }
  if (Math.abs(value) < 0.005) {
    return "+0.00";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function deltaTone(value: number | null): "positive" | "negative" | "neutral" {
  if (value === null || Math.abs(value) < 0.005) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}

function deltaIcon(value: number | null) {
  const tone = deltaTone(value);
  if (tone === "positive") {
    return <TrendingUp size={13} />;
  }
  if (tone === "negative") {
    return <TrendingDown size={13} />;
  }
  return <Minus size={13} />;
}

function pullRequestLabel(entry: LeaderboardEntry) {
  return entry.pullRequest.number === null ? "No PR" : `#${entry.pullRequest.number}`;
}

function pullRequestText(pullRequest: LeaderboardEntry["pullRequest"]) {
  return pullRequest.number === null ? "No PR" : `#${pullRequest.number}`;
}

function formatShortSha(value: string) {
  return value.length > 7 ? value.slice(0, 7) : value;
}

function formatBenchmarkVersion(value: string) {
  return value
    .replace(/^openrouter-vision-judge-/, "")
    .replace(/^imagent-/, "")
    .replace(/-/g, " ");
}

function formatDimension(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatModelName(value: string | null) {
  if (!value) {
    return "Unknown";
  }
  if (value === "google/gemini-3.1-flash-image") {
    return "Gemini 3.1 Flash Image";
  }
  return value.split("/").pop()?.replace(/[-_]+/g, " ") || value;
}

function scoreWidth(value: number) {
  return `${Math.max(2, Math.min(100, value))}%`;
}

function parseTimestamp(value: string) {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

const RELATIVE_TIME_MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
] as const;

function formatAbsoluteDate(timestamp: number) {
  const date = new Date(timestamp);
  return `${RELATIVE_TIME_MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}`;
}

function formatRelativeTime(value: string, referenceTime: number | null) {
  const timestamp = parseTimestamp(value);
  if (timestamp === null) {
    return "pending";
  }

  // Pre-mount (server render and first client render) `referenceTime` is null:
  // render a timezone-independent absolute date so both outputs match exactly.
  // The live "x ago" text takes over once the client clock is available.
  if (referenceTime === null) {
    return formatAbsoluteDate(timestamp);
  }

  const seconds = Math.max(0, Math.round((referenceTime - timestamp) / 1000));
  if (seconds < 10) {
    return "just now";
  }
  if (seconds < 60) {
    return `${seconds}s ago`;
  }

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days = Math.round(hours / 24);
  return `${days}d ago`;
}
