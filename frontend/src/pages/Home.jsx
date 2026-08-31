import { Link } from "react-router-dom";
import { Button, Card } from "../components/UI.jsx";
import RiskGauge from "../components/RiskGauge.jsx";
import usePageTitle from "../lib/usePageTitle.js";

const STEPS = [
  { label: "Upload", detail: "Bring a dataset and an optional auxiliary dataset an attacker might already hold." },
  { label: "Detect", detail: "Direct identifiers, quasi-identifiers and sensitive attributes are classified with visible confidence and reasons." },
  { label: "Attack", detail: "A real record-linkage simulation scores candidate matches between the two datasets." },
  { label: "Score", detail: "k-anonymity, uniqueness and linkage confidence combine into one transparent 0-100 risk score." },
  { label: "Fix", detail: "Generalization, bucketing and suppression are applied and ranked by risk-reduction vs utility loss." },
  { label: "Re-test", detail: "The same attack is re-run against the fixed data so the improvement is measured, not assumed." },
];

export default function Home() {
  usePageTitle("Home");
  return (
    <div>
      <div className="px-8 pt-16 pb-14 border-b border-border relative overflow-hidden">
        <div className="max-w-3xl relative z-10">
          <div className="text-accent-cyan text-[11px] font-mono tracking-widest uppercase mb-4">
            privacy red-team platform
          </div>
          <h1 className="font-display text-5xl font-semibold text-text-primary leading-[1.1] mb-5">
            Attack your own data<br />before someone else does.
          </h1>
          <p className="text-text-secondary text-base max-w-xl mb-8 leading-relaxed">
            PrivaLens DataRescue runs a real record-linkage attack against your "anonymized" dataset,
            scores exactly how re-identifiable it is, and rewrites the risky columns until the
            attack stops working — with every number traceable back to the data.
          </p>
          <div className="flex items-center gap-3">
            <Link to="/upload"><Button>Upload a dataset</Button></Link>
            <Link to="/demo"><Button variant="secondary">Run the demo instead</Button></Link>
          </div>
        </div>

        <div className="absolute right-8 top-10 hidden lg:flex flex-col items-center opacity-90">
          <span className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-1">
            Example output — not your data
          </span>
          <RiskGauge score={91.25} level="CRITICAL" size={260} />
        </div>
      </div>

      <div className="px-8 py-10">
        <h2 className="font-display font-semibold text-text-primary text-lg mb-6">How the pipeline works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {STEPS.map((s, i) => (
            <Card key={s.label} eyebrow={`0${i + 1}`} title={s.label}>
              <p className="text-text-secondary text-sm leading-relaxed">{s.detail}</p>
            </Card>
          ))}
        </div>
      </div>

      <div className="px-8 pb-14">
        <Card className="bg-bg-elevated">
          <p className="text-text-secondary text-sm leading-relaxed">
            <span className="text-text-primary font-medium">A note on scope: </span>
            PrivaLens gives a technical, evidence-grounded re-identification risk assessment
            under the configured attack scenarios. It does not certify legal compliance and does
            not guarantee a dataset is impossible to re-identify against attacks it wasn't
            tested against.
          </p>
        </Card>
      </div>
    </div>
  );
}
