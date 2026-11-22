import { useCallback, useEffect, useState } from "react";
import { countStates, titleOf } from "./fields";
import { Library, type Doc } from "./Library";
import { ModelPicker } from "./ModelPicker";
import { resultKey } from "./modelinfo";
import type { ModelList } from "./shiori.d.ts";
import { Processing } from "./Processing";
import { Setup } from "./Setup";
import { Workspace } from "./Workspace";
import type { Fixture } from "./types";

export function App() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [open, setOpen] = useState<Doc | null>(null);
  const [settings, setSettings] = useState(false);
  // Setup (D-100): opens by itself when no model is installed, and from the Models link. `null` = not showing.
  const [setup, setSetup] = useState<ModelList | null>(null);
  const [adding, setAdding] = useState<{ doc_id: string; name: string } | null>(null);

  useEffect(() => {
    fetch("./fixture.json")
      .then((r) => r.json() as Promise<Fixture>)
      .then((fx) => setDocs([{ fx, counts: countStates(fx) }]))
      .catch(() => setDocs([])); // no fixture: start with an empty Library
  }, []);

  useEffect(() => {
    void window.shiori?.listModels().then((l) => {
      if (!l.skipPicker && !l.models.some((m) => m.installed)) setSetup(l);
    });
  }, []);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setSettings(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  // Add document opens the model choice first; "Choose PDF" then starts processing with that model (D-99).
  const [picker, setPicker] = useState<{ list: ModelList; value: string | null; note: string | null } | null>(null);
  const start = async (modelId?: string) => {
    const r = await window.shiori?.startProcessing(modelId);
    if (r && "error" in r) return setPicker((p) => p && { ...p, note: "A document is still processing. Wait for it or cancel it before switching models." });
    setPicker(null);
    if (r) {
      setOpen(null);
      setAdding(r);
    }
  };
  const add = async () => {
    const list = await window.shiori?.listModels();
    if (!list) return;
    if (list.skipPicker) return start(); // dev checks (SHIORI_PICK) skip the dialog
    setPicker({ list, value: list.default, note: null });
  };
  const finished = useCallback((fx: Fixture) => {
    const d = { fx, counts: countStates(fx) };
    // One result per document and model: the same PDF run with another model is a separate row.
    setDocs((all) => [...(all ?? []).filter((x) => resultKey(x.fx.doc_id, x.fx.model_id) !== resultKey(fx.doc_id, fx.model_id)), d]);
    setAdding(null);
    setOpen(d);
  }, []);

  const name = open ? titleOf(open.fx) : null;
  return (
    <div className="app">
      <header className={`bar${navigator.userAgent.includes("Mac") ? " mac" : ""}`}>
        <span className="logo" aria-hidden>栞</span>
        <b className="brand">Shiori</b>
        <button className={`navlink${open ? "" : " on"}`} onClick={() => { setOpen(null); setAdding(null); setSetup(null); }}>Library</button>
        {window.shiori && <button className={`navlink${setup ? " on" : ""}`} onClick={() => void window.shiori?.listModels().then(setSetup)}>Models</button>}
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
      {picker && (
        <div className="scrim">
          <div className="dialog" role="dialog" aria-label="Add document">
            <b>Add document</b>
            <ModelPicker list={picker.list} value={picker.value} onChange={(id) => setPicker({ ...picker, value: id, note: null })} />
            {picker.list.running && picker.value && picker.value !== picker.list.running && <p className="meta">The running model is stopped and the new one loads first.</p>}
            {picker.note && <p className="err">{picker.note}</p>}
            <div className="drow">
              <button className="btn" onClick={() => setPicker(null)}>Cancel</button>
              <button className="btn primary" onClick={() => void start(picker.value ?? undefined)}>Choose PDF</button>
            </div>
          </div>
        </div>
      )}
      <main>
        {!docs && <div className="err">Loading</div>}
        {setup && <Setup list={setup} onRefresh={async () => setSetup((await window.shiori?.listModels()) ?? null)} onClose={() => setSetup(null)} />}
        {docs && !setup && adding && <Processing docId={adding.doc_id} name={adding.name} onDone={finished} onBack={() => setAdding(null)} />}
        {docs && !setup && !adding && !open && <Library docs={docs} onOpen={setOpen} onAdd={add} canAdd={!!window.shiori} />}
        {open && !setup && <Workspace fx={open.fx} counts={open.counts} />}
      </main>
    </div>
  );
}
