import { useState } from "react";
import { daysLeft, deadlineOf, issuerOf, titleOf } from "./fields";
import type { State } from "./status";
import type { Fixture } from "./types";

type Sort = "deadline" | "recent";
export type Doc = { fx: Fixture; counts: Record<State, number> };

export function Library({ docs, onOpen }: { docs: Doc[]; onOpen: (d: Doc) => void }) {
  const [sort, setSort] = useState<Sort>("deadline");
  const [q, setQ] = useState("");
  const [note, setNote] = useState("");

  const rows = docs
    .map((d, i) => ({ d, i, t: titleOf(d.fx), issuer: issuerOf(d.fx), due: deadlineOf(d.fx) }))
    .filter((r) => `${r.t.en ?? ""} ${r.t.ja ?? ""} ${r.issuer ?? ""}`.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) =>
      sort === "recent" ? b.i - a.i : (a.due ?? "9999").localeCompare(b.due ?? "9999") || a.i - b.i,
    );

  // Importing needs the pipeline, which this window does not run yet.
  const picked = (name: string) => setNote(`"${name}" was not opened. Adding documents is not connected yet.`);

  return (
    <div className="library">
      <div className="toprow">
        <div
          className="drop"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) picked(f.name);
          }}
        >
          <span>Drop a Japanese RFP PDF or choose a file</span>
          <label className="btn">
            Browse
            <input type="file" accept="application/pdf,.pdf" hidden onChange={(e) => e.target.files?.[0] && picked(e.target.files[0].name)} />
          </label>
        </div>
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
            const n = due ? daysLeft(due) : null;
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
                      {due}
                      <div className="meta">{n === null ? "" : n < 0 ? "Closed" : n === 0 ? "Due today" : `${n} days left`}</div>
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
