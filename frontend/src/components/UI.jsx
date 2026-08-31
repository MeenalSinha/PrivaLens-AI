export function Card({ children, className = "", title, eyebrow, action }) {
  return (
    <div className={`bg-bg-surface border border-border rounded-lg p-5 ${className}`}>
      {(title || eyebrow) && (
        <div className="flex items-center justify-between mb-4">
          <div>
            {eyebrow && (
              <div className="text-accent-cyan text-[11px] font-mono tracking-widest uppercase mb-1">
                {eyebrow}
              </div>
            )}
            {title && <h3 className="font-display font-semibold text-text-primary text-base">{title}</h3>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function Button({ children, variant = "primary", className = "", ...props }) {
  const variants = {
    primary: "bg-accent-cyan text-bg-primary hover:bg-accent-cyan/90 font-semibold",
    secondary: "bg-bg-elevated text-text-primary border border-border hover:border-border-light",
    ghost: "text-text-secondary hover:text-text-primary hover:bg-bg-elevated",
    danger: "bg-risk-critical/10 text-risk-critical border border-risk-critical/40 hover:bg-risk-critical/20",
  };
  return (
    <button
      className={`px-4 py-2 rounded-md text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Stat({ label, value, sub, valueClassName = "" }) {
  return (
    <div>
      <div className="text-text-muted text-xs uppercase tracking-widest font-mono mb-1">{label}</div>
      <div className={`font-mono text-2xl font-semibold text-text-primary ${valueClassName}`}>{value}</div>
      {sub && <div className="text-text-secondary text-xs mt-0.5">{sub}</div>}
    </div>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 border border-dashed border-border rounded-lg">
      <div className="w-10 h-10 rounded border border-border-light mb-4 flex items-center justify-center">
        <div className="w-2 h-2 bg-accent-cyan rounded-full" />
      </div>
      <h3 className="font-display font-semibold text-text-primary mb-1.5">{title}</h3>
      <p className="text-text-secondary text-sm max-w-sm mb-5">{description}</p>
      {action}
    </div>
  );
}

export function Loading({ label = "Processing" }) {
  return (
    <div className="flex items-center gap-3 text-text-secondary font-mono text-sm py-6">
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-cyan opacity-60" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent-cyan" />
      </span>
      {label}...
    </div>
  );
}

export function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="border border-risk-critical/40 bg-risk-critical/10 text-risk-critical text-sm rounded-md px-4 py-3 font-mono">
      {message}
    </div>
  );
}

/**
 * Structured error state: WHAT happened, WHY, WHAT TO DO NEXT. Prefer
 * this over the plain ErrorBanner for failures the user can act on
 * (upload rejected, attack couldn't run, etc). Falls back to a plain
 * message-only banner if only `what` is provided.
 */
export function ErrorCard({ what, why, next, action }) {
  if (!what) return null;
  return (
    <div className="border border-risk-critical/40 bg-risk-critical/10 rounded-md px-4 py-3">
      <div className="text-risk-critical text-sm font-medium">{what}</div>
      {why && <div className="text-text-secondary text-xs mt-1.5">{why}</div>}
      {next && <div className="text-text-secondary text-xs mt-1">{next}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/**
 * Before/after/change trio for a risk outcome. Replaces the invisible
 * opacity-0 RiskBadge spacer hack that previously shipped in
 * Mitigation.jsx - every value here comes from the actual computed
 * comparison, and the arrow/wording always matches the real sign of the
 * delta (never assumes improvement).
 */
export function RiskChangeSummary({ before, after }) {
  const delta = Math.round((before.risk_score - after.risk_score) * 100) / 100;
  const direction = delta > 0 ? "down" : delta < 0 ? "up" : "flat";
  const styles = {
    down: "text-risk-low",
    up: "text-risk-critical",
    flat: "text-text-secondary",
  };
  const arrow = { down: "\u2193", up: "\u2191", flat: "\u2192" }[direction];
  const label = {
    down: `${Math.abs(delta)} points lower`,
    up: `${Math.abs(delta)} points higher`,
    flat: "No material change",
  }[direction];

  return (
    <div className="grid grid-cols-3 gap-4 items-center">
      <div>
        <div className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-1">Before</div>
        <div className="font-mono text-lg text-text-primary">{before.risk_level} &middot; {before.risk_score}</div>
      </div>
      <div className="text-center">
        <div className={`font-mono text-2xl font-semibold ${styles[direction]}`}>{arrow} {label}</div>
      </div>
      <div>
        <div className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-1">After</div>
        <div className="font-mono text-lg text-text-primary">{after.risk_level} &middot; {after.risk_score}</div>
      </div>
    </div>
  );
}
