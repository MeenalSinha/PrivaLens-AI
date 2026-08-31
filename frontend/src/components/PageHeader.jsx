export default function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="border-b border-border px-8 py-6 flex items-start justify-between gap-6 bg-bg-primary/60 backdrop-blur sticky top-0 z-10">
      <div>
        {eyebrow && (
          <div className="text-accent-cyan text-[11px] font-mono tracking-widest uppercase mb-1.5">
            {eyebrow}
          </div>
        )}
        <h1 className="font-display text-2xl font-semibold text-text-primary">{title}</h1>
        {description && <p className="text-text-secondary text-sm mt-1.5 max-w-2xl">{description}</p>}
      </div>
      {action}
    </div>
  );
}
