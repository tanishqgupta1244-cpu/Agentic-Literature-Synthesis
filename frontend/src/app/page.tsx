"use client";

import { useHealthCheck } from "@/hooks/useHealthCheck";
import StatusIndicator from "@/components/StatusIndicator";

export default function HomePage() {
  const { backend, database, backendDetail, databaseDetail, refresh } =
    useHealthCheck();

  return (
    <main style={styles.main}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>Automated Literature Review</h1>
        <p style={styles.subtitle}>
          AI-powered research paper analysis &mdash; Phase 0
        </p>
      </div>

      {/* Status card */}
      <section style={styles.card} aria-label="System status">
        <div style={styles.cardHeader}>
          <span style={styles.cardTitle}>System Status</span>
          <button
            style={styles.refreshBtn}
            onClick={refresh}
            aria-label="Refresh status"
            title="Refresh"
          >
            ↻ Refresh
          </button>
        </div>

        <div style={styles.statusList}>
          <StatusIndicator
            label="Backend"
            status={backend}
            detail={backendDetail}
          />
          <StatusIndicator
            label="Database"
            status={database}
            detail={databaseDetail}
          />
        </div>
      </section>

      {/* Phase notice */}
      <p style={styles.notice}>
        Phase 0 &mdash; Environment &amp; Foundation only.
        <br />
        PDF upload, agents and report generation are not yet implemented.
      </p>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  main: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "32px",
    padding: "48px 24px",
    width: "100%",
    maxWidth: "520px",
    margin: "0 auto",
  },
  header: {
    textAlign: "center",
  },
  title: {
    fontSize: "26px",
    fontWeight: 700,
    color: "#e8eaf0",
    letterSpacing: "-0.3px",
  },
  subtitle: {
    marginTop: "8px",
    fontSize: "14px",
    color: "#8b8fa8",
  },
  card: {
    width: "100%",
    background: "#1a1d27",
    border: "1px solid #2a2d3e",
    borderRadius: "12px",
    padding: "20px",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
  },
  cardTitle: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#8b8fa8",
    textTransform: "uppercase",
    letterSpacing: "0.8px",
  },
  refreshBtn: {
    background: "transparent",
    border: "1px solid #2a2d3e",
    color: "#8b8fa8",
    borderRadius: "6px",
    padding: "4px 10px",
    fontSize: "12px",
    cursor: "pointer",
  },
  statusList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  notice: {
    textAlign: "center",
    fontSize: "12px",
    color: "#4b4f66",
    lineHeight: 1.6,
  },
};
