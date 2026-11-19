import { Fragment, useEffect, useState } from "react";
import { groupOf, labelOf, STATES } from "./fields";
import { MachineEn } from "./MachineEn";
import { PdfView, type Find } from "./PdfView";
import { SummaryPanel } from "./SummaryPanel";
import { STATE_TEXT, stateOf, unusualSection, type State } from "./status";
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
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = () =>
      void ask([]).then((n) => {
        if (!live) return;
        take(n);
        if (working(n)) timer = setTimeout(poll, 1500);
      });
    poll();
    return () => {
      live = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fx.doc_id]);

  const trNote = (f: Field) => {
    if (tr.status === "unavailable") return <p className="meta">{unavailableText(tr.reason)}</p>;
    if (tr.status === "ok" && idsOf(f, fx).some((id) => !(id in tr.items))) {
      return tr.failed.some((id) => idsOf(f, fx).includes(id)) && !working(tr) ? <p className="meta">{unavailableText("failed")}</p> : <p className="meta">Translating</p>;
    }
    return null;
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

  // The Japanese sentences behind a field, grouped by list item when the field is a list.
  const sources = (f: Field) => {
    const groups = f.items.length ? f.items.map((i) => ({ en: i.text_en, ids: i.citations })) : [{ en: null, ids: f.citations }];
    return groups.map((g, n) => (
      <div className="srcgroup" key={n}>
        {g.en && <MachineEn text={g.en} note={null} />}
        {g.ids.map((id) => {
          const s = fx.sentences[id];
          const line = tr.status === "ok" ? enLine(tr.items[id]) : null;
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
