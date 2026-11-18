import { useEffect, useState } from "react";
import { countStates, titleOf } from "./fields";
import { Library, type Doc } from "./Library";
import { Workspace } from "./Workspace";
import type { Fixture } from "./types";

export function App() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [open, setOpen] = useState<Doc | null>(null);
  const [settings, setSettings] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("./fixture.json")
      .then((r) => r.json() as Promise<Fixture>)
      .then((fx) => setDocs([{ fx, counts: countStates(fx) }]))
      .catch((e: unknown) => setErr(String(e)));
  }, []);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setSettings(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  const name = open ? titleOf(open.fx) : null;
  return (
    <div className="app">
      <header className={`bar${navigator.userAgent.includes("Mac") ? " mac" : ""}`}>
        <span className="logo" aria-hidden>栞</span>
        <b className="brand">Shiori</b>
        <button className={`navlink${open ? "" : " on"}`} onClick={() => setOpen(null)}>Library</button>
        {open && <span className="docname" title={name?.ja ?? undefined}>{name?.en ?? name?.ja ?? "Document"}</span>}
        <span className="grow" />
        {open && <button className="btn" disabled title="Export is not available yet">Export</button>}
        <button className="btn sq" aria-label="Settings" aria-expanded={settings} onClick={() => setSettings(!settings)}>⚙</button>
      </header>
      {settings && (
        <div className="pop" role="dialog" aria-label="Settings">
          <b>Settings</b>
          <p className="meta">There is nothing to set yet.</p>
        </div>
      )}
      <main>
        {err && <div className="err">No fixture: {err}. Run scripts/export_app_fixture.py.</div>}
        {!err && !docs && <div className="err">Loading</div>}
        {docs && !open && <Library docs={docs} onOpen={setOpen} />}
        {open && <Workspace fx={open.fx} counts={open.counts} />}
      </main>
    </div>
  );
}
