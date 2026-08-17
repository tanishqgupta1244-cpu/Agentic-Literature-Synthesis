import type { CheckStatus } from "@/lib/api";

interface Props {
  label: string;
  status: CheckStatus;
  detail: string;
}

const DOT: Record<CheckStatus, { color: string; symbol: string; text: string }> = {
  checking: { color: "#eab308", symbol: "◌", text: "Checking…" },
  ok:       { color: "#22c55e", symbol: "●", text: "Connected" },
  error:    { color: "#ef4444", symbol: "●", text: "Error"     },
};

export default function StatusIndicator({ label, status, detail }: Props) {
  const dot = DOT[status];

  return (
    <div style={styles.row}>
      <span style={styles.label}>{label}</span>
      <span style={{ ...styles.dot, color: dot.color }} aria-hidden="true">
        {dot.symbol}
      </span>
      <span
        style={{ ...styles.detail, color: dot.color }}
        role="status"
        aria-label={`${label}: ${detail}`}
      >
        {detail}
      </span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  row: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "14px 20px",
    background: "#1a1d27",
    borderRadius: "8px",
    border: "1px solid #2a2d3e",
  },
  label: {
    width: "96px",
    fontSize: "14px",
    color: "#8b8fa8",
    fontWeight: 500,
    flexShrink: 0,
  },
  dot: {
    fontSize: "16px",
    lineHeight: 1,
  },
  detail: {
    fontSize: "14px",
    fontWeight: 600,
  },
};
