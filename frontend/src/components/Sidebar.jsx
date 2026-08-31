import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useDataset } from "../context/DatasetContext.jsx";

const NAV = [
  { to: "/", label: "Home", icon: "H" },
  { to: "/upload", label: "Upload", icon: "U" },
  { to: "/profiler", label: "Profiler", icon: "P" },
  { to: "/dashboard", label: "Risk Dashboard", icon: "R" },
  { to: "/attack", label: "Attack Simulation", icon: "A" },
  { to: "/vulnerabilities", label: "Vulnerability Explorer", icon: "V" },
  { to: "/mitigation", label: "Fix & Re-test", icon: "F" },
  { to: "/comparison", label: "Before / After", icon: "B" },
  { to: "/report", label: "Report", icon: "D" },
  { to: "/demo", label: "Demo Mode", icon: "M" },
  { to: "/rescue", label: "DataRescue", icon: "X" },
];

function SidebarContents({ mainDataset, onNavigate }) {
  return (
    <>
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md border border-accent-cyan/50 flex items-center justify-center relative overflow-hidden">
            <div className="w-2.5 h-2.5 rounded-full bg-accent-cyan" />
          </div>
          <span className="font-display font-semibold text-text-primary text-[15px] tracking-tight">
            PrivaLens<span className="text-accent-cyan">DataRescue</span>
          </span>
        </div>
        <p className="text-text-muted text-[11px] mt-1.5 font-mono">privacy red-team platform</p>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-3">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm mb-0.5 transition-colors ${
                isActive
                  ? "bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-elevated border border-transparent"
              }`
            }
          >
            <span className="w-5 h-5 rounded border border-current/30 flex items-center justify-center text-[10px] font-mono shrink-0">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-border">
        <div className="text-text-muted text-[11px] font-mono uppercase tracking-widest mb-1.5">
          Active Dataset
        </div>
        <div className="text-text-secondary text-xs truncate">
          {mainDataset ? mainDataset.name : "None loaded"}
        </div>
      </div>
    </>
  );
}

export default function Sidebar() {
  const { mainDataset } = useDataset();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  // Close the drawer automatically whenever the route changes.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Escape closes the mobile drawer, matching the same convention used
  // for expandable rows elsewhere in the app.
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  return (
    <>
      {/* Mobile top bar with hamburger trigger - shown below the lg breakpoint */}
      <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-bg-surface sticky top-0 z-30">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md border border-accent-cyan/50 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-accent-cyan" />
          </div>
          <span className="font-display font-semibold text-text-primary text-sm">
            PrivaLens<span className="text-accent-cyan">DataRescue</span>
          </span>
        </div>
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation menu"
          aria-expanded={mobileOpen}
          className="w-9 h-9 flex items-center justify-center rounded-md border border-border text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-cyan"
        >
          <span aria-hidden="true" className="font-mono text-lg leading-none">&#9776;</span>
        </button>
      </div>

      {/* Backdrop overlay for the mobile drawer */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={`lg:hidden fixed top-0 left-0 h-screen w-72 max-w-[85vw] bg-bg-surface border-r border-border z-50 flex flex-col transition-transform duration-200
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
      >
        <div className="flex justify-end px-3 pt-3">
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation menu"
            className="w-8 h-8 flex items-center justify-center rounded-md border border-border text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-cyan"
          >
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <SidebarContents mainDataset={mainDataset} onNavigate={() => setMobileOpen(false)} />
      </aside>

      {/* Persistent desktop sidebar */}
      <aside className="hidden lg:flex w-60 shrink-0 border-r border-border bg-bg-surface h-screen sticky top-0 flex-col">
        <SidebarContents mainDataset={mainDataset} />
      </aside>
    </>
  );
}
