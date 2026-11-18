import { useEffect, useState } from "react";
import { PdfView } from "./PdfView";
import { STATE_TEXT, stateOf } from "./status";
import type { Field, Fixture } from "./types";

type Active = { id: string; field: Field } | null;

export function App() {
  const [fx, setFx] = useState<Fixture | null>(null);
  const [active, setActive] = useState<Active>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("./fixture.json")
      .then((r) => r.json() as Promise<Fixture>)
      .then(setFx)
      .catch((e: unknown) => setErr(String(e)));
  }, []);

  if (err) return <div className="err">No fixture: {err}. Run scripts/export_app_fixture.py.</div>;
  if (!fx) return <div className="err">Loading</div>;
  const sent = active ? fx.sentences[active.id] : undefined;
  const item = active?.field.items.find((i) => i.citations.includes(active.id));
  const en = item?.text_en ?? active?.field.value_en;
  const ja = item?.text_ja ?? active?.field.value_ja;
  return (
    <div className="layout">
      <aside className="fields">
        {fx.fields.map((f) => {
          const state = stateOf(f, fx.sentences);
          return (
            <section key={f.field} className="field">
              <h3>
                {f.field} <span className={`st st-${state}`}>{STATE_TEXT[state]}</span>
              </h3>
              {f.value_en && <p>{f.value_en}</p>}
              {f.items.map((i, n) => i.text_en && <p key={n}>• {i.text_en}</p>)}
              <div>
                {f.citations.map((id) => {
                  const s = fx.sentences[id];
                  return (
                    <button
                      key={id}
                      className={`chip${active?.id === id && active.field === f ? " on" : ""}${s ? "" : " missing"}`}
                      title={s ? id : `${id} (missing)`}
                      onClick={() => setActive({ id, field: f })}
                    >
                      {s ? `p${s.page}` : "missing"}
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </aside>
      <div className="right">
        {active && (
          <div className="detail">
            <b>{active.field.field}</b> · {active.id}
            {sent ? ` · page ${sent.page}` : " · sentence missing from fixture"}
            <div className="ja" lang="ja">{sent?.text_orig ?? "(no text)"}</div>
            <div className="en">{en ?? "(no English value)"}</div>
            {ja && <div className="sec" lang="ja">extracted (ja): {ja}</div>}
            <div className="sec">
              section: {sent?.section_path.map((p, i) => `${p} ${sent.section_titles[i] ?? ""}`).join(" > ") || "none"}
            </div>
            <div className="sec">
              checks: {active.field.checks.map((c) => `${c.name} ${c.passed ? "ok" : "FAILED"}`).join(", ") || "none stored"}
            </div>
          </div>
        )}
        <PdfView url={fx.pdf} active={sent ?? null} />
      </div>
    </div>
  );
}
