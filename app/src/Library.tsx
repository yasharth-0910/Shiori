import { useState } from "react";
import { issuerOf, titleOf } from "./fields";
import { stateOf, type State } from "./status";
import { bidDeadline, type Due } from "./summary";
import type { Fixture } from "./types";

type Sort = "deadline" | "recent";
export type Doc = { fx: Fixture; counts: Record<State, number> };

// Soonest upcoming deadline first, then closed ones (most recent first), then documents with none.
const dueKey = (due: Due | null) => (!due ? 1e9 : due.days >= 0 ? due.days : 1e6 - due.days);

type Props = { docs: Doc[]; onOpen: (d: Doc) => void; onAdd: () => Promise<void>; canAdd: boolean };

export function Library({ docs, onOpen, onAdd, canAdd }: Props) {
  const [sort, setSort] = useState<Sort>("deadline");
  const [q, setQ] = useState("");
  const [note, setNote] = useState("");

  const rows = docs
    .map((d, i) => ({ d, i, t: titleOf(d.fx), issuer: issuerOf(d.fx), due: bidDeadline(d.fx, (f) => stateOf(f, d.fx.sentences)) }))
    .filter((r) => `${r.t.en ?? ""} ${r.t.ja ?? ""} ${r.issuer ?? ""}`.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) =>
      sort === "recent" ? b.i - a.i : dueKey(a.due) - dueKey(b.due) || a.i - b.i,
    );

  const add = async () => {
    try {
      await onAdd();
      setNote("");
    } catch {
      setNote("Could not start processing. Is the sidecar available?");
    }
  };

  return (
    <div className="library">
      <div className="toprow">
        <button className="btn primary" disabled={!canAdd} title={canAdd ? "" : "Only available in the desktop app"} onClick={() => void add()}>
          Add document
        </button>
        <input className="input search" placeholder="Search documents" aria-label="Search documents" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg" role="group" aria-label="Sort">
          <button className={sort === "deadline" ? "on" : ""} onClick={() => setSort("deadline")}>Deadline</button>
          <button className={sort === "recent" ? "on" : ""} onClick={() => setSort("recent")}>Recently added</button>
        </div>
      </div>
      {note && <p className="meta">{note}</p>}
      <table className="ledger">
        <thead>
          <tr>
            <th>Title</th>
            <th>Issuer</th>
            <th>Deadline</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map(({ d, t, issuer, due }) => {
            const n = due ? due.days : null;
            return (
              <tr key={d.fx.doc_id}>
                <td>
                  <div className="t-en">{t.en ?? "Untitled"}</div>
                  {t.ja && <div className="t-ja" lang="ja">{t.ja}</div>}
                </td>
                <td>{issuer ?? "—"}</td>
                <td className="num">
                  {due ? (
                    <>
                      {due.when}
                      <div className="meta">{n === null ? "" : n < 0 ? "Closed" : n === 0 ? "Due today" : n === 1 ? "1 day left" : `${n} days left`}</div>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  <div className="stack">
                    {d.counts.verified > 0 && <span className="pill pill-verified">{d.counts.verified} verified</span>}
                    {d.counts.needs_review > 0 && <span className="pill pill-needs_review">{d.counts.needs_review} need review</span>}
                    {d.counts.other_document > 0 && <span className="pill pill-other_document">{d.counts.other_document} see other document</span>}
                  </div>
                </td>
                <td>
                  <button className="btn primary" onClick={() => onOpen(d)}>Open</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && <p className="empty">No documents.</p>}
    </div>
  );
}
