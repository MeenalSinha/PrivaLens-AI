import { Routes, Route, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import AuditStepper from "./components/AuditStepper.jsx";

import Home from "./pages/Home.jsx";
import Upload from "./pages/Upload.jsx";
import Profiler from "./pages/Profiler.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import AttackSimulation from "./pages/AttackSimulation.jsx";
import VulnerabilityExplorer from "./pages/VulnerabilityExplorer.jsx";
import Mitigation from "./pages/Mitigation.jsx";
import Comparison from "./pages/Comparison.jsx";
import Report from "./pages/Report.jsx";
import Demo from "./pages/Demo.jsx";
import RescueJobs from "./pages/RescueJobs.jsx";
import RescueJobDetail from "./pages/RescueJobDetail.jsx";
import NotFound from "./pages/NotFound.jsx";

// The stepper tracks the core Upload->Report PrivaLens pipeline - it has
// no concept of DataRescue's separate agent workflow, so showing it on
// /rescue pages would just be confusing, disconnected clutter (a second
// navigation system competing with the rescue job's own stage tracker).
function ConditionalStepper() {
  const location = useLocation();
  if (location.pathname.startsWith("/rescue")) return null;
  return <AuditStepper />;
}

export default function App() {
  return (
    <div className="flex flex-col lg:flex-row min-h-screen bg-bg-primary bg-grid-pattern bg-grid">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <ConditionalStepper />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/profiler" element={<Profiler />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/attack" element={<AttackSimulation />} />
          <Route path="/vulnerabilities" element={<VulnerabilityExplorer />} />
          <Route path="/mitigation" element={<Mitigation />} />
          <Route path="/comparison" element={<Comparison />} />
          <Route path="/report" element={<Report />} />
          <Route path="/demo" element={<Demo />} />
          <Route path="/rescue" element={<RescueJobs />} />
          <Route path="/rescue/:jobId" element={<RescueJobDetail />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
