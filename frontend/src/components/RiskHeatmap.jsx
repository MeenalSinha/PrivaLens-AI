/**
 * Generic accessible heatmap. Renders as a real <table> (inherently
 * screen-reader friendly - a colored <div> grid would not be), with a
 * text legend and a title-attribute tooltip per cell. Every value
 * rendered must come from the caller's real analysis data - this
 * component has no logic that invents numbers.
 *
 * cells: 2D array matching rows x columns, each entry:
 *   { display: string, intensity: 0-1, tooltip?: string }
 * intensity drives color: 0 = low risk (teal), 1 = high risk (red),
 * matching the existing risk color vocabulary rather than a decorative
 * rainbow.
 */
const STOPS = [
  { t: 0.0, rgb: [63, 214, 199] },   // risk-low
  { t: 0.5, rgb: [232, 179, 57] },   // risk-moderate
  { t: 0.75, rgb: [232, 118, 60] },  // risk-high
  { t: 1.0, rgb: [226, 76, 76] },    // risk-critical
];

function colorForIntensity(t) {
  const clamped = Math.max(0, Math.min(1, t));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const a = STOPS[i], b = STOPS[i + 1];
    if (clamped >= a.t && clamped <= b.t) {
      const localT = (clamped - a.t) / (b.t - a.t || 1);
      const rgb = a.rgb.map((c, idx) => Math.round(c + (b.rgb[idx] - c) * localT));
      return `rgb(${rgb.join(",")})`;
    }
  }
  return `rgb(${STOPS[STOPS.length - 1].rgb.join(",")})`;
}

export default function RiskHeatmap({ title, rowLabel, columnLabel, rows, columns, cells, legendLabels }) {
  if (!rows.length || !columns.length) {
    return <p className="text-text-secondary text-sm">Not enough data to render a heatmap yet.</p>;
  }

  return (
    <div>
      {title && <div className="text-text-muted text-[11px] font-mono uppercase tracking-widest mb-3">{title}</div>}
      <div className="overflow-x-auto">
        <table className="border-separate" style={{ borderSpacing: "3px" }}>
          <caption className="sr-only">
            {title || "Risk heatmap"}: {rowLabel} by {columnLabel}, cell intensity indicates risk contribution.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="text-left text-text-muted text-[10px] font-mono uppercase pr-3 pb-2 sticky left-0 bg-bg-surface">
                {rowLabel}
              </th>
              {columns.map((col) => (
                <th
                  key={col}
                  scope="col"
                  className="text-text-muted text-[10px] font-mono uppercase pb-2 px-1 text-center whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={row}>
                <th
                  scope="row"
                  className="text-right text-text-secondary text-xs font-mono pr-3 whitespace-nowrap sticky left-0 bg-bg-surface"
                >
                  {row}
                </th>
                {columns.map((col, ci) => {
                  const cell = cells[ri]?.[ci];
                  if (!cell) return <td key={col} className="w-9 h-9 bg-bg-elevated rounded" />;
                  return (
                    <td
                      key={col}
                      title={cell.tooltip || `${row} \u00d7 ${col}: ${cell.display}`}
                      className="w-9 h-9 rounded text-center align-middle"
                      style={{ backgroundColor: colorForIntensity(cell.intensity) }}
                    >
                      <span className="text-[10px] font-mono font-semibold text-bg-primary/80">{cell.display}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-4 mt-4 text-[11px] font-mono text-text-muted">
        <span>{legendLabels?.[0] || "Lower risk"}</span>
        <div className="flex h-2.5 w-32 rounded overflow-hidden">
          {Array.from({ length: 20 }, (_, i) => (
            <div key={i} style={{ backgroundColor: colorForIntensity(i / 19), flex: 1 }} />
          ))}
        </div>
        <span>{legendLabels?.[1] || "Higher risk"}</span>
      </div>
    </div>
  );
}
