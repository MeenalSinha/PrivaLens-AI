import { useRef } from "react";

/**
 * A keyboard-accessible expand/collapse trigger. Renders as a real
 * semantic element (button-like div with role="button") so it can be
 * reached by Tab, activated with Enter/Space, and closed with Escape -
 * fixing a real bug where AttackSimulation match rows, Profiler
 * classification rows, and VulnerabilityExplorer cluster cards were
 * plain <div>/<tr> onClick handlers invisible to keyboard and
 * screen-reader users.
 *
 * Usage: wrap the clickable summary content. Pass `as="tr"` for table
 * rows (keeps valid table structure) or leave default for a div.
 */
export default function Expandable({
  as: Tag = "div",
  expanded,
  onToggle,
  onClose,
  className = "",
  children,
  ariaLabel,
}) {
  const ref = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onToggle();
    } else if (e.key === "Escape" && expanded) {
      e.preventDefault();
      onClose ? onClose() : onToggle();
      ref.current?.blur();
    }
  };

  return (
    <Tag
      ref={ref}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      aria-label={ariaLabel}
      onClick={onToggle}
      onKeyDown={handleKeyDown}
      className={`cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-cyan focus-visible:outline-offset-[-2px] ${className}`}
    >
      {children}
    </Tag>
  );
}
