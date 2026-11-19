import { useEffect, useState } from "react";
import type { Fixture } from "./types";

// What the sidecar reports, in pipeline order. `extract` (the model) is skipped until llama-server is wired in.
const STAGES = ["ingest", "segment", "retrieve", "extract", "verify"] as const;

type Props = { docId: string; name: string; onDone: (fx: Fixture) => void; onBack: () => void };

export function Processing({ docId, name, onDone, onBack }: Props) {
  const [stage, setStage] = useState("queued");
  const [pages, setPages] = useState<number | null>(null);
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
    return () => {
      live = false;
    };
  }, [docId, onDone]);

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
            {STAGES.map((s, i) => (
              <li key={s} className={stage === s ? "now" : at > i || stage === "done" ? "past" : ""}>
                {s}
              </li>
            ))}
          </ol>
          <p className="meta">Stage: {stage}</p>
        </>
      )}
    </div>
  );
}
