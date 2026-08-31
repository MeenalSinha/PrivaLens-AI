const STYLES = {
  LOW: "text-risk-low border-risk-low/40 bg-risk-low/10",
  MODERATE: "text-risk-moderate border-risk-moderate/40 bg-risk-moderate/10",
  HIGH: "text-risk-high border-risk-high/40 bg-risk-high/10",
  CRITICAL: "text-risk-critical border-risk-critical/40 bg-risk-critical/10",
};

export default function RiskBadge({ level, className = "" }) {
  const style = STYLES[level] || STYLES.MODERATE;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border font-mono text-xs tracking-wide uppercase ${style} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {level}
    </span>
  );
}
