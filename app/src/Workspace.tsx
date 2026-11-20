import { useEffect, useState } from "react";
import { groupOf, labelOf, STATES } from "./fields";
import { collapsedLine, scalarAnswer, worthShowing, type En } from "./fieldview";
import { MachineEn } from "./MachineEn";
import { PdfView, type Find } from "./PdfView";
import { SummaryPanel } from "./SummaryPanel";
import { deadlineLine } from "./summary";
import { STATE_TEXT, docTypeText, stateOf, unusualSection, type State } from "./status";
import { enLine, idsOf, progressNote, unavailableText, working, type TrState } from "./translate";
import type { Field, Fixture } from "./types";

type Tab = "summary" | "fields" | "deadlines";
const TABS: [Tab, string][] = [
  ["summary", "Summary"],
  ["fields", "Fields"],
  ["deadlines", "Deadlines"],
];

const Pill = ({ s }: { s: State }) => <span className={`pill pill-${s}`}>{STATE_TEXT[s]}</span>;

// One value line per field: the English value, or a count for list fields. Never invented.
function summaryOf(f: Field): string {
  if (f.value_en) return f.value_en;
  return f.items.length ? `${f.items.length} ${f.items.length === 1 ? "entry" : "entries"}` : "";
}

// A quiet bar while a sentence waits for its English. Never the word "Translating".
const Wait = () => <div className="enwait" aria-hidden="true" />;

export function Workspace({ fx, counts }: { fx: Fixture; counts: Record<State, number> }) {
  const [tab, setTab] = useState<Tab>("fields");
  const [filter, setFilter] = useState<State | null>(null);
  const [text, setText] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [sid, setSid] = useState<string | null>(null);
  const [find, setFind] = useState<Find | null>(null);
  const [hitCount, setHitCount] = useState(0);
  const [copied, setCopied] = useState<string | null>(null);
  // English for the cited sentences comes from the sidecar's background queue (D-88). The Workspace opens
  // without it, asks once on mount (which restarts a cancelled queue), polls while the queue works, and
  // asks again with a field's sentence ids when that field is opened, which moves them to the front.
  const [tr, setTr] = useState<TrState>({ status: "loading" });

  const ask = (ids: string[]): Promise<TrState> => {
    if (!window.shiori) return Promise.resolve({ status: "unavailable", reason: "no_document" });
    return window.shiori.translate(fx.doc_id, ids).then(
      (r): TrState => (r.ok ? { status: "ok", items: r.items, done: r.done, total: r.total, failed: r.failed } : { status: "unavailable", reason: r.reason }),
      (): TrState => ({ status: "unavailable", reason: "failed" }),
    );
  };
  // A slower, older answer never replaces a newer one.
  const take = (n: TrState) => setTr((p) => (p.status === "ok" && n.status === "ok" && n.done < p.done ? p : n));

  useEffect(() => {
    void ask([]).then(take);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fx.doc_id]);

  // Poll while the queue has work. Depends on `tick` too, so it keeps going after a field's retry restarts a finished queue.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!working(tr)) return;
    const t = setTimeout(() => void ask([]).then((n) => { take(n); setTick((x) => x + 1); }), 1500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tr, tick]);

  // Why English will not come, or null. Waiting is not an error: that is drawn as a placeholder bar.
  const trNote = (f: Field) => {
    if (tr.status === "unavailable") return <p className="meta">{unavailableText(tr.reason)}</p>;
    if (tr.status === "ok" && !working(tr) && tr.failed.some((id) => idsOf(f, fx).includes(id))) return <p className="meta">{unavailableText("failed")}</p>;
    return null;
  };
  const waiting = (ids: string[]) => tr.status === "loading" || (tr.status === "ok" && ids.some((id) => !(id in tr.items)) && working(tr));
  const trItems = tr.status === "ok" ? tr.items : null;

  // One English line: model text carries the label (and the numbers/name note), code-made text does not.
  const enView = (e: En, big: boolean) =>
    e.mt ? (
      <MachineEn text={e.text} note={e.tr ? (enLine(e.tr)?.note ?? null) : null} big={big} />
    ) : (
      <div className={`${big ? "answer big" : "answer"}${e.ja ? " ja" : ""}`} lang={e.ja ? "ja" : undefined}>{e.text}</div>
    );

  // The collapsed card's one line: the entry count (lists) and the English answer, or a placeholder while it is coming.
  const collapsed = (f: Field) => {
    const l = collapsedLine(f, trItems, deadlineLine);
    if (l.en && !worthShowing(l.en.text, labelOf(f), null)) l.en = null; // an English line that is just the field name says nothing
    const ids = f.items.length ? (f.items[0]?.citations ?? []) : f.citations;
    return (
      <div className="fvalue">
        {l.count && <span className="count">{l.count}</span>}
        {l.en ? enView(l.en, true) : ids.length > 0 && waiting(ids) ? <Wait /> : null}
      </div>
    );
  };

  const toggle = (f: Field) => {
    setFind(null);
    if (open === f.field) {
      setOpen(null);
      setSid(null);
    } else {
      setOpen(f.field);
      setSid(f.citations.find((id) => id in fx.sentences) ?? null);
      if (tr.status !== "unavailable") void ask(idsOf(f, fx)).then(take);
    }
  };

  const q = text.trim().toLowerCase();
  const shown = fx.fields.filter(
    (f) =>
      (!filter || stateOf(f, fx.sentences) === filter) &&
      (!q || `${labelOf(f)} ${summaryOf(f)}`.toLowerCase().includes(q)),
  );
  const groups = [...new Set(shown.map(groupOf))].map((g) => [g, shown.filter((f) => groupOf(f) === g)] as const);

  const copy = (f: Field, lines: string[]) => {
    void navigator.clipboard.writeText(lines.join("\n")).then(
      () => {
        setCopied(f.field);
        setTimeout(() => setCopied((c) => (c === f.field ? null : c)), 1500);
      },
      () => setCopied(null),
    );
  };

  // An opened card: a deterministic answer on top when it adds something, then one block per cited sentence:
  // its own English line (labelled) directly above its Japanese, then the page chip and section path.
  // The block is a button that jumps the PDF to the highlight.
  const block = (id: string) => {
    const s = fx.sentences[id];
    const line = trItems?.[id] ? enLine(trItems[id]) : null;
    return (
      <button key={id} className={`src${sid === id ? " on" : ""}`} onClick={() => s && setSid(id)} disabled={!s}>
        {line ? <MachineEn text={line.text} note={line.note} /> : s && waiting([id]) ? <Wait /> : null}
        <span className="ja" lang="ja">{s?.text_orig ?? "Sentence missing from this export."}</span>
        {s && (
          <span className="srcmeta">
            <span className="pgchip">p. {s.page}</span>
            <span className="meta">{s.section_path.map((p, i) => `${p} ${s.section_titles[i] ?? ""}`.trim()).join(" > ") || "No section"}</span>
          </span>
        )}
      </button>
    );
  };
  const sources = (f: Field) => {
    const label = labelOf(f);
    const firstEn = (ids: string[]) => ids.map((id) => trItems?.[id]?.en).find((x) => x) ?? null;
    // Scalar: one group, its answer is value_en or the enum label. List: one group per item, its answer is
    // the code-made line (deadlines) or the item's own English.
    const groups: { ans: En | null; ids: string[] }[] = f.items.length
      ? f.items.map((i) => ({ ans: ((m) => (m ? { text: m, mt: false } : i.text_en ? { text: i.text_en, mt: true } : null))(deadlineLine(i)), ids: i.citations }))
      : [{ ans: scalarAnswer(f, trItems), ids: f.citations }];
    return groups.map((g, n) => {
      const ids = g.ids.filter((id) => id in fx.sentences);
      const top = g.ans && worthShowing(g.ans.text, label, firstEn(ids)) ? g.ans : null;
      return (
        <div className="srcgroup" key={n}>
          {top && enView(top, true)}
          {top?.tr && f.value_ja && <div className="javal" lang="ja">{f.value_ja}</div>}
          {g.ids.map(block)}
        </div>
      );
    });
  };

  const sentence = sid ? (fx.sentences[sid] ?? null) : null;
  const doFind = (e: React.FormEvent<HTMLFormElement>, cur: Find | null) => {
    e.preventDefault();
    const v = String(new FormData(e.currentTarget).get("q") ?? "");
    setSid(null);
    setFind(cur && cur.q === v ? { q: v, step: cur.step + 1 } : { q: v, step: 0 });
  };

  return (
    <div className="work">
      <section className="left">
        <div className="tabs" role="tablist">
          {TABS.map(([t, label]) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {label}
            </button>
          ))}
          {fx.doc_type && (
            <span className="dtype" title="Guessed from the first page. A wrong guess changes which fields are looked for.">
              Read as: {docTypeText(fx.doc_type)}
            </span>
          )}
        </div>
        {tab === "deadlines" && <p className="empty">Nothing here yet.</p>}
        {tab === "summary" && (
          <SummaryPanel
            fx={fx}
            onCite={(id) => {
              setFind(null);
              setSid(id);
            }}
          />
        )}
        {tab === "fields" && (
          <>
            <div className="counts">
              <button className={filter === null ? "on" : ""} onClick={() => setFilter(null)}>
                All {fx.fields.length}
              </button>
              {STATES.map((s) => (
                <button key={s} className={filter === s ? "on" : ""} onClick={() => setFilter(filter === s ? null : s)}>
                  {STATE_TEXT[s]} {counts[s]}
                </button>
              ))}
            </div>
            {progressNote(tr) && <p className="meta">{progressNote(tr)}</p>}
            <input className="input" placeholder="Filter fields" aria-label="Filter fields" value={text} onChange={(e) => setText(e.target.value)} />
            <div className="list">
              {groups.length === 0 && <p className="empty">No fields match.</p>}
              {groups.map(([g, fs]) => (
                <div key={g}>
                  <h3 className="group">{g}</h3>
                  {fs.map((f) => {
                    const st = stateOf(f, fx.sentences);
                    const isOpen = open === f.field;
                    return (
                      <div key={f.field} className={`field${isOpen ? " open" : ""}`}>
                        <button className="fhead" aria-expanded={isOpen} onClick={() => toggle(f)}>
                          <span className="flabel">{labelOf(f)}</span>
                          <Pill s={st} />
                          {!isOpen && st !== "not_found" && collapsed(f)}
                        </button>
                        {isOpen && (
                          <div className="fbody">
                            {st === "not_found" ? (
                              <>
                                <p>The document does not state this.</p>
                                <form className="findbox" onSubmit={(e) => doFind(e, find)}>
                                  <input className="input" name="q" aria-label="Find in document" placeholder="Find in document" />
                                  <button className="btn" type="submit">Find</button>
                                </form>
                                {find && (
                                  <p className="meta">
                                    {hitCount ? `Match ${(find.step % hitCount) + 1} of ${hitCount}. Press Find for the next one.` : "No matches."}
                                  </p>
                                )}
                              </>
                            ) : (
                              <>
                                {trNote(f)}
                                {sources(f)}
                                {unusualSection(f) && <p className="meta">Found in an unusual section.</p>}
                                <button
                                  className="btn"
                                  onClick={() =>
                                    copy(
                                      f,
                                      [...new Set([...f.citations, ...f.items.flatMap((i) => i.citations)])].flatMap((id) => fx.sentences[id]?.text_orig ?? []),
                                    )
                                  }
                                >
                                  {copied === f.field ? "Copied" : "Copy"}
                                </button>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </>
        )}
      </section>
      <PdfView url={fx.pdf} active={sentence} find={find} onFindCount={setHitCount} />
    </div>
  );
}
