import { useEffect, useState } from "react";
import type { Fixture } from "./types";

// The stage keys the sidecar (and main, for loading_model) send, in order, with their plain-English names.
// The keys are not changed here; this map is the only place the names live.
const STEPS: [key: string, name: string][] = [
  ["loading_model", "Loading the model"],
  ["ingest", "Reading the PDF"],
  ["segment", "Splitting it into sentences"],
  ["retrieve", "Finding candidate sentences"],
  ["extract", "Extracting fields"],
  ["verify", "Checking every citation"],
];

type Props = { docId: string; name: string; onDone: (fx: Fixture) => void; onBack: () => void };

// "eligibility (2 of 3)" -> { n: 2, m: 3 }; null when the detail has no count.
const progressOf = (detail: string | null): { n: number; m: number } | null => {
  const r = detail && /\((\d+) of (\d+)\)/.exec(detail);
  return r && Number(r[2]) > 0 ? { n: Number(r[1]), m: Number(r[2]) } : null;
};

export function Processing({ docId, name, onDone, onBack }: Props) {
  const [stage, setStage] = useState("queued");
  const [pages, setPages] = useState<number | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [secs, setSecs] = useState(0);
  const [model, setModel] = useState(false); // the model was loaded for this document
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const api = window.shiori;
    if (!api) return;
    let live = true;
    const tick = async () => {
      try {
        const s = await api.getStatus(docId);
        if (!live) return;
        setStage(s.stage);
        setPages(s.pages);
        setDetail(s.detail);
        if (s.stage === "loading_model") setModel(true);
        if (s.stage === "failed") return setError(s.error ?? "unknown");
        if (s.stage === "done") {
          const fx = await api.getFields(docId);
          // The PDF is served by id through shiori://, relative like the cMaps.
          if (live) onDone({ ...fx, pdf: `doc/${docId}.pdf` });
          return;
        }
        setTimeout(() => void tick(), 400);
      } catch {
        if (live) setError("lost_contact");
      }
    };
    void tick();
    const t0 = Date.now();
    const clock = setInterval(() => setSecs(Math.floor((Date.now() - t0) / 1000)), 500);
    return () => {
      live = false;
      clearInterval(clock);
    };
  }, [docId, onDone]);

  // main puts "Model not set up" / "Model failed to start (code)" in the detail while the model is missing.
  const noModel = !!detail && /^Model (not set up|failed to start)/.test(detail);
  const steps = STEPS.filter(([k]) => k !== "loading_model" || (model && !noModel));
  const at = steps.findIndex(([k]) => k === stage);
  const prog = stage === "extract" ? progressOf(detail) : null;
  const sub = noModel ? null : stage === "extract" && detail ? `Extracting ${detail}` : detail;
  const mmss = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;

  return (
    <div className="processing">
      <div className="pcard">
        <h2 className="pname">{name}</h2>
        {error ? (
          <>
            <p className="err">Processing failed ({error}).</p>
            <button className="btn" onClick={onBack}>Back to Library</button>
          </>
        ) : (
          <>
            <p className="meta">{pages ? `${pages} ${pages === 1 ? "page" : "pages"}` : "Starting"}</p>
            {noModel && <p className="pnotice">Running without the model. Some fields will show Not found.</p>}
            <ol className="stepper" data-stage={stage}>
              {steps.map(([k, label], i) => {
                const st = stage === "done" || (at >= 0 && at > i) ? "done" : at === i ? "active" : "pending";
                return (
                  <li key={k} className={`step ${st}`} data-step={k} aria-current={st === "active" ? "step" : undefined}>
                    <span className="mark" aria-hidden="true">{st === "done" ? "✓" : ""}</span>
                    <div className="stepbody">
                      <span className="steplabel">{label}</span>
                      {st === "active" && sub && <span className="meta">{sub}</span>}
                      {st === "active" && prog && (
                        <div className="bar2" role="progressbar" aria-valuemin={0} aria-valuemax={prog.m} aria-valuenow={prog.n}>
                          <div style={{ width: `${Math.min(100, (prog.n / prog.m) * 100)}%` }} />
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
            <p className="meta pfoot">Elapsed {mmss}</p>
            <p className="meta">Everything stays on this computer.</p>
          </>
        )}
      </div>
    </div>
  );
}
