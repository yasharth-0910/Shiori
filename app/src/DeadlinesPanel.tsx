import { deadlineRows } from "./deadlines";
import { STATE_TEXT, stateOf } from "./status";
import { formatWhen } from "./summary";
import type { Fixture } from "./types";

// One row per deadline item, sorted by date. A row is a button that calls the same cite function as the
// Fields view and the Summary chips, so the PDF opens at the cited sentence with the highlight.
export function DeadlinesPanel({ fx, onCite }: { fx: Fixture; onCite: (sid: string) => void }) {
  const rows = deadlineRows(fx, (f) => stateOf(f, fx.sentences), formatWhen);
  if (rows.length === 0) {
    const f = fx.fields.find((x) => x.field === "deadlines");
    const other = f && stateOf(f, fx.sentences) === "other_document";
    return (
      <div className="list">
        <p className="empty">
          No deadlines were found in this document. Check the notice or bid instructions.
          {other && <> <span className="pill pill-other_document">{STATE_TEXT.other_document}</span></>}
        </p>
      </div>
    );
  }
  return (
    <div className="list">
      <ul className="dllist">
        {rows.map((r) => (
          <li key={r.key}>
            <button className="dlrow" data-sid={r.sid ?? undefined} disabled={!r.sid} onClick={() => r.sid && onCite(r.sid)} aria-label={`${r.kind}: show the source${r.page ? ` on page ${r.page}` : ""}`}>
              <span className="dlkind">{r.kind}</span>
              <span className={`pill pill-${r.state}`}>{STATE_TEXT[r.state]}</span>
              <span className="dlwhen">{r.when ?? "No date stored"}</span>
              {r.ja && <span className="ja" lang="ja">{r.ja}</span>}
              {r.page && <span className="pgchip">p. {r.page}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
