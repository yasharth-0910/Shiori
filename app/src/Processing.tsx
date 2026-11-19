import { useEffect, useRef, useState } from "react";
import { labelOf } from "./fields";
import type { ProcEvent } from "./shiori.d";
import type { Field, Fixture } from "./types";

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

const VISIBLE = 6; // cards shown in the live stream
const STORED = 200; // events kept in memory
const label = (id: string) => labelOf({ field: id } as Field);

type Props = { docId: string; name: string; onDone: (fx: Fixture) => void; onBack: () => void };

// "eligibility (2 of 3)" -> { n: 2, m: 3 }; null when the detail has no count.
const progressOf = (detail: string | null): { n: number; m: number } | null => {
  const r = detail && /\((\d+) of (\d+)\)/.exec(detail);
  return r && Number(r[2]) > 0 ? { n: Number(r[1]), m: Number(r[2]) } : null;
};

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function EventCard({ e }: { e: ProcEvent }) {
  if (e.kind === "candidates")
    return (
      <li className="ev">
        <div className="evhead">
          <b>Candidates</b>
          <span className="meta">{label(e.field)}</span>
        </div>
        <p className="meta evsub">
          {e.count} {e.count === 1 ? "sentence" : "sentences"} found · first one: page {e.page}
          {e.section ? ` · ${e.section}` : ""}
        </p>
        <p className="evja" lang="ja">{e.text}</p>
      </li>
    );
  if (e.kind === "answer")
    return (
      <li className="ev">
        <div className="evhead">
          <b>Answer</b>
          <span className="meta">{label(e.field)}</span>
        </div>
        <p className="evja" lang="ja">{e.value_ja}</p>
        {e.page != null && <p className="meta evsub">page {e.page}</p>}
      </li>
    );
  const [cls, text] = e.exact === true ? ["ok", "Exact span match"] : e.exact === false ? ["warn", "Not an exact match"] : ["none", "No span check"];
  return (
    <li className="ev">
      <div className="evhead">
        <b>Check</b>
        <span className="meta">{label(e.field)}</span>
        <span className={`evbadge ${cls}`}>{text}</span>
      </div>
    </li>
  );
}

export function Processing({ docId, name, onDone, onBack }: Props) {
  const [stage, setStage] = useState("queued");
  const [pages, setPages] = useState<number | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [secs, setSecs] = useState(0);
  const [model, setModel] = useState<string | null>(null); // the model file's name, when one is set up
  const [loaded, setLoaded] = useState(false); // the model was loaded for this document
  const [loadSecs, setLoadSecs] = useState<number | null>(null); // measured here: main does the loading
  const [stepSecs, setStepSecs] = useState<Record<string, number>>({});
  const [sentences, setSentences] = useState<number | null>(null);
  const [answered, setAnswered] = useState(0);
  const [total, setTotal] = useState<number | null>(null);
  const [events, setEvents] = useState<ProcEvent[]>([]); // oldest first, capped at STORED
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queue = useRef<ProcEvent[]>([]); // fetched, not shown yet: events arrive in bursts, cards are revealed one by one
  const finished = useRef<Fixture | null>(null);
  const back = useRef(onBack); // App passes a new function each render; the polling effect must not restart for it
  back.current = onBack;

  useEffect(() => {
    const api = window.shiori;
    if (!api) return;
    let live = true;
    let since = 0;
    let loadStart: number | null = null;
    const tick = async () => {
      try {
        const s = await api.getStatus(docId, since);
        if (!live) return;
        since = s.cursor;
        queue.current.push(...s.events);
        setStage(s.stage);
        setPages(s.pages);
        setDetail(s.detail);
        setModel(s.model ?? null);
        if (s.seconds) setStepSecs(s.seconds);
        if (s.sentences != null) setSentences(s.sentences);
        if (s.fields_total != null) setTotal(s.fields_total);
        if (s.answered != null) setAnswered(s.answered);
        if (s.stage === "loading_model") {
          setLoaded(true);
          loadStart ??= Date.now();
        } else if (loadStart !== null) {
          setLoadSecs(Math.round((Date.now() - loadStart) / 100) / 10);
          loadStart = null;
        }
        if (s.stage === "cancelled") return back.current();
        if (s.stage === "failed") return setError(s.error ?? "unknown");
        if (s.stage === "done") {
          const fx = await api.getFields(docId);
          if (!live) return;
          // Only the last few cards will be seen: older ones go straight to the stored list.
          const old = queue.current.splice(0, Math.max(0, queue.current.length - VISIBLE));
          if (old.length) setEvents((e) => [...e, ...old].slice(-STORED));
          // The PDF is served by id through shiori://, relative like the cMaps.
          finished.current = { ...fx, pdf: `doc/${docId}.pdf` };
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
    // Reveal queued events one at a time (two at a time when many wait). When the run is over and the
    // queue is empty, hold the screen a moment so the last results can be read, then open the document.
    let hold: ReturnType<typeof setTimeout> | undefined;
    const reveal = setInterval(() => {
      const q = queue.current;
      if (q.length) {
        const next = q.splice(0, q.length > 8 ? 2 : 1);
        setEvents((e) => [...e, ...next].slice(-STORED));
      } else if (finished.current && hold === undefined) {
        const fx = finished.current;
        hold = setTimeout(() => live && onDone(fx), 1200);
      }
    }, 300);
    return () => {
      live = false;
      clearInterval(clock);
      clearInterval(reveal);
      clearTimeout(hold);
    };
  }, [docId, onDone]);

  const cancel = () => {
    setCancelling(true);
    window.shiori?.cancel(docId).catch(() => setCancelling(false));
  };

  // main puts "Model not set up" / "Model failed to start (code)" in the detail while the model is missing.
  const noModel = !!detail && /^Model (not set up|failed to start)/.test(detail);
  const steps = STEPS.filter(([k]) => k !== "loading_model" || (loaded && !noModel));
  const at = steps.findIndex(([k]) => k === stage);
  const prog = stage === "extract" ? progressOf(detail) : null;
  const sub = noModel ? null : stage === "extract" && detail ? `Extracting ${detail}` : detail;
  const running = stage !== "done" && !finished.current;
  const issuer = [...events].reverse().find((e) => e.kind === "answer" && e.field === "issuer_org");
  const shown = events.slice(-VISIBLE).reverse(); // newest on top

  if (error)
    return (
      <div className="processing one">
        <div className="pcard">
          <h2 className="pname">{name}</h2>
          <p className="err">Processing failed ({error}).</p>
          <button className="btn" onClick={back.current}>Back to Library</button>
        </div>
      </div>
    );

  return (
    <div className="processing">
      <div className="pcard">
        <h2 className="pname">{name}</h2>
        <p className="meta">
          {pages ? `${pages} ${pages === 1 ? "page" : "pages"}` : "Starting"}
          {sentences != null && ` · ${sentences} sentences`}
        </p>
        {(model || issuer?.kind === "answer") && (
          <div className="pchips">
            {issuer?.kind === "answer" && <span className="pchip" lang="ja">{issuer.value_ja}</span>}
            {model && <span className="pchip mono" title="Model file">{model}</span>}
          </div>
        )}
        {noModel && <p className="pnotice">Running without the model. Some fields will show Not found.</p>}
        <ol className="stepper" data-stage={stage}>
          {steps.map(([k, text], i) => {
            const st = stage === "done" || (at >= 0 && at > i) ? "done" : at === i ? "active" : "pending";
            const took = k === "loading_model" ? loadSecs : stepSecs[k];
            return (
              <li key={k} className={`step ${st}`} data-step={k} aria-current={st === "active" ? "step" : undefined}>
                <span className="mark" aria-hidden="true">{st === "done" ? "✓" : ""}</span>
                <div className="stepbody">
                  <span className="steplabel">{text}</span>
                  {st === "active" && sub && <span className="meta">{sub}</span>}
                  {st === "active" && prog && (
                    <div className="bar2" role="progressbar" aria-valuemin={0} aria-valuemax={prog.m} aria-valuenow={prog.n}>
                      <div style={{ width: `${Math.min(100, (prog.n / prog.m) * 100)}%` }} />
                    </div>
                  )}
                </div>
                {st === "done" && took != null && <span className="took">{took.toFixed(1)} s</span>}
              </li>
            );
          })}
        </ol>
        {total != null && <p className="meta">Fields answered {answered} of {total}</p>}
        <div className="pfoot">
          <span className="meta">
            {at >= 0 && stage !== "done" ? `Step ${at + 1} of ${steps.length} · ` : ""}Elapsed {mmss(secs)}
          </span>
          <button className="btn" onClick={cancel} disabled={cancelling || !running}>
            {cancelling ? "Cancelling" : "Cancel"}
          </button>
        </div>
      </div>
      <section className="stream" aria-label="Live results">
        <h3 className="streamhead">Live results</h3>
        <ul className="evlist" aria-live="polite">
          {running && (
            <li className="ev scan" aria-label="Waiting for the next result">
              <span className="sk" />
              <span className="sk short" />
            </li>
          )}
          {shown.map((e) => (
            <EventCard key={e.n} e={e} />
          ))}
        </ul>
      </section>
    </div>
  );
}
