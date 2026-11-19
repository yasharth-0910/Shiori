import { useCallback, useEffect, useState } from "react";
import { countStates, titleOf } from "./fields";
import { Library, type Doc } from "./Library";
import { Processing } from "./Processing";
import { Workspace } from "./Workspace";
import type { Fixture } from "./types";

export function App() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [open, setOpen] = useState<Doc | null>(null);
  const [settings, setSettings] = useState(false);
  const [adding, setAdding] = useState<{ doc_id: string; name: string } | null>(null);

  useEffect(() => {
    fetch("./fixture.json")
      .then((r) => r.json() as Promise<Fixture>)
      .then((fx) => setDocs([{ fx, counts: countStates(fx) }]))
      .catch(() => setDocs([])); // no fixture: start with an empty Library
  }, []);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setSettings(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  const add = async () => {
    const r = await window.shiori?.startProcessing();
    if (r) {
      setOpen(null);
      setAdding(r);
    }
  };
  const finished = useCallback((fx: Fixture) => {
    const d = { fx, counts: countStates(fx) };
    setDocs((all) => [...(all ?? []), d]);
    setAdding(null);
    setOpen(d);
  }, []);

  const name = open ? titleOf(open.fx) : null;
  return (
    <div className="app">
      <header className={`bar${navigator.userAgent.includes("Mac") ? " mac" : ""}`}>
        <span className="logo" aria-hidden>栞</span>
        <b className="brand">Shiori</b>
        <button className={`navlink${open ? "" : " on"}`} onClick={() => { setOpen(null); setAdding(null); }}>Library</button>
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
        {!docs && <div className="err">Loading</div>}
        {docs && adding && <Processing docId={adding.doc_id} name={adding.name} onDone={finished} onBack={() => setAdding(null)} />}
        {docs && !adding && !open && <Library docs={docs} onOpen={setOpen} onAdd={add} canAdd={!!window.shiori} />}
        {open && <Workspace fx={open.fx} counts={open.counts} />}
      </main>
    </div>
  );
}
