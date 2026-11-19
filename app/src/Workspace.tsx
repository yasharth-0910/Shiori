import { Fragment, useState } from "react";
import { groupOf, labelOf, STATES } from "./fields";
import { MachineEn } from "./MachineEn";
import { PdfView, type Find } from "./PdfView";
import { SummaryPanel } from "./SummaryPanel";
import { STATE_TEXT, stateOf, unusualSection, type State } from "./status";
import { enLine, idsOf, unavailableText, type TrState } from "./translate";
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

export function Workspace({ fx, counts }: { fx: Fixture; counts: Record<State, number> }) {
  const [tab, setTab] = useState<Tab>("fields");
  const [filter, setFilter] = useState<State | null>(null);
  const [text, setText] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [sid, setSid] = useState<string | null>(null);
  const [find, setFind] = useState<Find | null>(null);
  const [hitCount, setHitCount] = useState(0);
  const [copied, setCopied] = useState<string | null>(null);
  const [tr, setTr] = useState<Record<string, TrState>>({}); // by field id; asked when a field is opened, never before

  const translateField = (f: Field) => {
    const ids = idsOf(f, fx);
    if (!ids.length || tr[f.field]) return;
    const set = (v: TrState) => setTr((t) => ({ ...t, [f.field]: v }));
    if (!window.shiori) return set({ status: "unavailable", reason: "no_document" });
    set({ status: "loading" });
    window.shiori.translate(fx.doc_id, ids).then(
      (r) => set(r.ok ? { status: "ok", items: r.items } : { status: "unavailable", reason: r.reason }),
      () => set({ status: "unavailable", reason: "failed" }),
    );
  };

  const trNote = (f: Field) => {
    const t = tr[f.field];
    if (t?.status === "loading") return <p className="meta">Translating</p>;
    return t?.status === "unavailable" ? <p className="meta">{unavailableText(t.reason)}</p> : null;
  };

  const toggle = (f: Field) => {
    setFind(null);
    if (open === f.field) {
      setOpen(null);
      setSid(null);
    } else {
      setOpen(f.field);
      setSid(f.citations.find((id) => id in fx.sentences) ?? null);
      translateField(f);
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

  // The Japanese sentences behind a field, grouped by list item when the field is a list.
  const sources = (f: Field) => {
    const groups = f.items.length ? f.items.map((i) => ({ en: i.text_en, ids: i.citations })) : [{ en: null, ids: f.citations }];
    return groups.map((g, n) => (
      <div className="srcgroup" key={n}>
        {g.en && <MachineEn text={g.en} note={null} />}
        {g.ids.map((id) => {
          const s = fx.sentences[id];
          const t = tr[f.field];
          const line = t?.status === "ok" ? enLine(t.items[id]) : null;
          return (
            <Fragment key={id}>
            {line && <MachineEn text={line.text} note={line.note} />}
            <button className={`src${sid === id ? " on" : ""}`} onClick={() => s && setSid(id)} disabled={!s}>
              <span className="ja" lang="ja">{s?.text_orig ?? "Sentence missing from this export."}</span>
              {s && (
                <span className="meta">
                  Section {s.section_path.map((p, i) => `${p} ${s.section_titles[i] ?? ""}`.trim()).join(" > ") || "none"} · page {s.page}
                </span>
              )}
            </button>
            </Fragment>
          );
        })}
      </div>
    ));
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
                          <span className="fvalue">{summaryOf(f)}</span>
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
