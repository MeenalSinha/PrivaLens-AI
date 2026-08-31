const COLORS = {
  LOW: "#3FD6C7",
  MODERATE: "#E8B339",
  HIGH: "#E8763C",
  CRITICAL: "#E24C4C",
};

// Semicircular instrument-dial gauge, 0-100, with tick marks like a lab
// meter. This is the product's signature visual element.
export default function RiskGauge({ score = 0, level = "LOW", size = 220 }) {
  const clamped = Math.max(0, Math.min(100, score));
  const angle = -90 + (clamped / 100) * 180; // -90deg (left) to +90deg (right)
  const color = COLORS[level] || COLORS.MODERATE;
  const radius = size / 2 - 18;
  const cx = size / 2;
  const cy = size / 2;

  const ticks = Array.from({ length: 11 }, (_, i) => i * 10);

  const polarToCartesian = (r, deg) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const needleAngleDeg = angle; // -90..90 mapped from 0..100 relative to top

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 1.65} viewBox={`0 0 ${size} ${size / 1.65}`}>
        {/* background arc */}
        <path
          d={describeArc(cx, cy, radius, -90, 90)}
          fill="none"
          stroke="#1E2732"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* value arc */}
        <path
          d={describeArc(cx, cy, radius, -90, needleAngleDeg)}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* tick marks */}
        {ticks.map((t) => {
          const tickAngle = -90 + (t / 100) * 180;
          const outer = polarToCartesian(radius + 12, tickAngle);
          const inner = polarToCartesian(radius + 4, tickAngle);
          return (
            <line
              key={t}
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke="#34424F"
              strokeWidth="1.5"
            />
          );
        })}
        {/* needle */}
        <g style={{ transition: "transform 0.6s ease" }} transform={`rotate(${needleAngleDeg}, ${cx}, ${cy})`}>
          <line x1={cx} y1={cy} x2={cx} y2={cy - radius + 8} stroke={color} strokeWidth="2.5" />
        </g>
        <circle cx={cx} cy={cy} r="5" fill={color} />
      </svg>
      <div className="-mt-2 text-center">
        <div className="font-mono text-4xl font-semibold" style={{ color }}>
          {clamped.toFixed(1)}
        </div>
        <div className="text-text-muted text-xs tracking-widest uppercase mt-1">Risk Score / 100</div>
      </div>
    </div>
  );
}

function polarToCartesianStatic(cx, cy, r, deg) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesianStatic(cx, cy, r, endAngle);
  const end = polarToCartesianStatic(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}
