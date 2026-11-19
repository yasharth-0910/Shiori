import { useEffect, useState } from "react";
import type { Fixture } from "./types";

// What the sidecar reports, in pipeline order. `extract` is the model; without one it stays idle.
const STAGES = ["ingest", "segment", "retrieve", "extract", "verify"] as const;

type Props = { docId: string; name: string; onDone: (fx: Fixture) => void; onBack: () => void };

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

  // "Loading model", then "Extracting eligibility (1 of 3)"; other stages show their name and any detail.
  const line =
    stage === "loading_model"
      ? "Loading model"
      : stage === "extract" && detail
        ? `Extracting ${detail}`
        : `Stage: ${stage}${detail ? ` (${detail})` : ""}`;
  const at = STAGES.indexOf(stage as (typeof STAGES)[number]);
  return (
    <div className="processing">
      <h2>{name}</h2>
      {error ? (
        <>
          <p className="err">Processing failed ({error}).</p>
          <button className="btn" onClick={onBack}>Back to Library</button>
        </>
      ) : (
        <>
          <p className="meta">{pages ? `${pages} pages` : "Starting"}</p>
          <ol className="stages">
            {model && <li className={stage === "loading_model" ? "now" : "past"}>model</li>}
            {STAGES.map((s, i) => (
              <li key={s} className={stage === s ? "now" : at > i || stage === "done" ? "past" : ""}>
                {s}
              </li>
            ))}
          </ol>
          <p className="meta">{line} · {secs} s</p>
        </>
      )}
    </div>
  );
}
