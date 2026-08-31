import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorBanner, Loading } from "../components/UI.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import { api } from "../api/client.js";
import usePageTitle from "../lib/usePageTitle.js";

function Dropzone({ label, description, onFile, busy, loadedName }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      onClick={() => inputRef.current?.click()}
      className={`border-2 border-dashed rounded-lg px-6 py-10 text-center cursor-pointer transition-colors ${
        dragOver ? "border-accent-cyan bg-accent-cyan/5" : "border-border hover:border-border-light"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.parquet"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
      />
      <div className="font-display font-semibold text-text-primary mb-1">{label}</div>
      <p className="text-text-secondary text-sm mb-3">{description}</p>
      {busy ? (
        <Loading label="Uploading" />
      ) : loadedName ? (
        <div className="inline-flex items-center gap-2 text-accent-cyan font-mono text-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" /> {loadedName} loaded
        </div>
      ) : (
        <div className="text-text-muted text-xs font-mono">CSV or Parquet, up to 10MB — click or drop here</div>
      )}
    </div>
  );
}

export default function Upload() {
  usePageTitle("Upload");
  const navigate = useNavigate();
  const { mainDataset, setMainDataset, auxDataset, setAuxDataset } = useDataset();
  const [busyMain, setBusyMain] = useState(false);
  const [busyAux, setBusyAux] = useState(false);
  const [error, setError] = useState(null);

  const uploadMain = async (file) => {
    setError(null);
    setBusyMain(true);
    try {
      const res = await api.uploadDataset(file, "main");
      setMainDataset({ id: res.dataset_id, name: file.name, profile: res.profile });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyMain(false);
    }
  };

  const uploadAux = async (file) => {
    setError(null);
    setBusyAux(true);
    try {
      const res = await api.uploadDataset(file, "auxiliary");
      setAuxDataset({ id: res.dataset_id, name: file.name, profile: res.profile });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyAux(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Step 1"
        title="Upload your datasets"
        description="Upload the dataset you want assessed, plus an optional auxiliary dataset representing what an attacker might already know. CSV or Parquet, up to 10MB each."
      />

      <div className="px-8 py-8 max-w-4xl">
        {error && <div className="mb-6"><ErrorBanner message={error} /></div>}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <Dropzone
            label="Target dataset"
            description="The dataset you believe is anonymized or de-identified."
            onFile={uploadMain}
            busy={busyMain}
            loadedName={mainDataset?.name}
          />
          <Dropzone
            label="Auxiliary dataset (optional)"
            description="A public or leaked dataset an attacker could cross-reference."
            onFile={uploadAux}
            busy={busyAux}
            loadedName={auxDataset?.name}
          />
        </div>

        {mainDataset && (
          <Card eyebrow="Loaded" title={mainDataset.name} className="mb-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-sm">
              <div>
                <div className="text-text-muted text-xs uppercase">Rows</div>
                <div className="text-text-primary">{mainDataset.profile.row_count}</div>
              </div>
              <div>
                <div className="text-text-muted text-xs uppercase">Columns</div>
                <div className="text-text-primary">{mainDataset.profile.column_count}</div>
              </div>
              <div>
                <div className="text-text-muted text-xs uppercase">Duplicate rows</div>
                <div className="text-text-primary">{mainDataset.profile.duplicate_rows}</div>
              </div>
              <div>
                <div className="text-text-muted text-xs uppercase">Missing cells</div>
                <div className="text-text-primary">{mainDataset.profile.total_missing_cells}</div>
              </div>
            </div>
          </Card>
        )}

        <div className="flex items-center gap-3">
          <Button disabled={!mainDataset} onClick={() => navigate("/profiler")}>
            Continue to Profiler
          </Button>
          <span className="text-text-muted text-xs">
            No auxiliary dataset? You can still profile and classify columns — the attack
            simulation just needs one before it can run.
          </span>
        </div>
      </div>
    </div>
  );
}
