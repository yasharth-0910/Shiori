import { labelOf } from "./fields";
import { stateOf } from "./status";
import { buildSummary } from "./summary";
import type { Fixture } from "./types";

// Lines are templates over Verified fields only; each ends with a page chip that opens the cited sentence.
export function SummaryPanel({ fx, onCite }: { fx: Fixture; onCite: (sid: string) => void }) {
  const { lines, unused } = buildSummary(fx, (f) => stateOf(f, fx.sentences));
  const byId = new Map(fx.fields.map((f) => [f.field, f]));
  return (
    <div className="list">
      {lines.length === 0 && <p className="empty">No verified fields to summarize yet.</p>}
      <ul className="sumlines">
        {lines.map((l) => (
          <li key={l.key}>
            {l.text}{" "}
            <button className="btn sq" aria-label={`Show the source on page ${l.page}`} onClick={() => onCite(l.sid)}>
              p. {l.page}
            </button>
          </li>
        ))}
      </ul>
      {unused.length > 0 && (
        <>
          <h3 className="group">Not stated or needs review</h3>
          <ul className="sumlines">
            {unused.map((u) => (
              <li key={u.field}>
                {byId.get(u.field) ? labelOf(byId.get(u.field)!) : u.field}
                {u.note && <span className="meta"> ({u.note})</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
