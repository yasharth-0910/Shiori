import { useEffect, useState } from "react";
import { PdfView } from "./PdfView";
import type { Citation, Field, Fixture } from "./types";

const STATUS: Record<Field["status"], string> = {
  present: "found",
  absent: "not found",
  see_other_document: "see other document",
};

export function App() {
  const [fx, setFx] = useState<Fixture | null>(null);
  const [active, setActive] = useState<Citation | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("./fixture.json")
      .then((r) => r.json() as Promise<Fixture>)
      .then(setFx)
      .catch((e: unknown) => setErr(String(e)));
  }, []);

  if (err) return <div className="err">No fixture: {err}. Run scripts/export_app_fixture.py.</div>;
  if (!fx) return <div className="err">Loading</div>;
  return (
    <div className="layout">
      <aside className="fields">
        {fx.fields.map((f) => (
          <section key={f.field} className="field">
            <h3>
              {f.field} <span className={`st st-${f.status}`}>{STATUS[f.status]}</span>
            </h3>
            {f.value_en && <p>{f.value_en}</p>}
            <div>
              {f.citations.map((c) => (
                <button
                  key={c.id}
                  className={`chip${active?.id === c.id ? " on" : ""}`}
                  title={c.text_ja}
                  onClick={() => setActive(c)}
                >
                  p{c.page} {c.id}
                </button>
              ))}
            </div>
          </section>
        ))}
      </aside>
      <PdfView url={fx.pdf} active={active} />
    </div>
  );
}
