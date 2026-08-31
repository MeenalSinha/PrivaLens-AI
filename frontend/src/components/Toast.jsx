import { useEffect } from "react";

/**
 * Minimal self-dismissing toast. Respects prefers-reduced-motion via the
 * global CSS rule in index.css (animation-duration collapses to ~0).
 */
export default function Toast({ message, tone = "success", onDismiss, duration = 4000 }) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onDismiss, duration);
    return () => clearTimeout(t);
  }, [message, duration, onDismiss]);

  if (!message) return null;

  const toneStyles = {
    success: "border-risk-low/40 bg-risk-low/10 text-risk-low",
    info: "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan",
    warning: "border-risk-moderate/40 bg-risk-moderate/10 text-risk-moderate",
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-md border font-mono text-sm shadow-lg transition-opacity ${toneStyles[tone] || toneStyles.info} bg-bg-elevated`}
    >
      {message}
    </div>
  );
}
