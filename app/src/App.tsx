import { useCallback, useEffect, useRef, useState } from "react";
import { countStates, titleOf } from "./fields";
import { Library } from "./Library";
import { ModelPicker } from "./ModelPicker";
import { Onboarding } from "./Onboarding";
import { showOnboarding, type Stage } from "./firstrun";
import type { ModelList, StorageInfo } from "./shiori.d.ts";
import {
  afterYes, askAfterFinish, askAtStartup, emptyText, markFailed, QUESTION, removedIds, savedIds, showQuestion, storeNotes, withDemo, withFinished, withoutDocs, withRows, type Doc,
} from "./saving";
import { Processing } from "./Processing";
import { Settings } from "./Settings";
import { Setup } from "./Setup";
import { Workspace } from "./Workspace";
import type { Fixture } from "./types";

export function App() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [open, setOpen] = useState<Doc | null>(null);
  const [settings, setSettings] = useState(false);
  // Setup (D-100): opens by itself when no model is installed, and from the Models link. `null` = not showing.
  const [setup, setSetup] = useState<ModelList | null>(null);
  const [stage, setStage] = useState<Stage>("intro"); // intro | find | ready are the onboarding (D-115); models is the Models page
  const [adding, setAdding] = useState<{ doc_id: string; name: string } | null>(null);

  // Saved documents (D-123). `info` stays null until getStorage is needed: it can raise a keyring prompt.
  const [info, setInfo] = useState<StorageInfo | null>(null);
  const infoRef = useRef(info);
  infoRef.current = info;
  const [finishedAny, setFinishedAny] = useState(false);
  const [storeError, setStoreError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [unread, setUnread] = useState(false); // the last getStorage failed
  const askStorage = useCallback(async () => {
    try {
      const i = (await window.shiori?.getStorage()) ?? null;
      setInfo(i);
      setUnread(false);
      return i;
    } catch {
      setUnread(true);
      setStoreError("Shiori could not read the saved documents.");
      return null;
    }
  }, []);

  useEffect(() => {
    fetch("./fixture.json")
      .then((r) => r.json() as Promise<Fixture>)
      .then((fx) => {
        const demo = { fx, counts: countStates(fx) };
        setDocs((all) => withDemo(all ?? [], demo));
      })
      .catch(() => setDocs((all) => all ?? [])); // no fixture: start with an empty Library
  }, []);

  useEffect(() => {
    void window.shiori?.listDocuments().then(
      (list) => {
        const rows = list.documents.map((fx) => ({ fx, counts: countStates(fx), saved: true }));
        if (rows.length) setDocs((all) => withRows(all ?? [], rows));
        if (askAtStartup(list)) void askStorage(); // nothing saved: getStorage is not asked at startup
      },
      () => setStoreError("Shiori could not read the saved documents."),
    );
  }, [askStorage]);

  useEffect(() => {
    void window.shiori?.listModels().then((l) => {
      if (showOnboarding(l)) {
        setStage("intro");
        setSetup(l);
      }
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
  // Stable: Processing's polling restarts when this function changes.
  const finished = useCallback((fx: Fixture) => {
    const d = { fx, counts: countStates(fx) };
    // One result per document and model: the same PDF run with another model is a separate row.
    setDocs((all) => withFinished(all ?? [], d));
    setAdding(null);
    setOpen(d);
    setFinishedAny(true);
    if (askAfterFinish(infoRef.current)) void askStorage().then((i) => i && setDocs((all) => markFailed(all ?? [], fx, i)));
  }, [askStorage]);

  // One storage action at a time; whatever happened, the state is read again.
  const act = async (failed: string, op: (api: NonNullable<Window["shiori"]>) => Promise<boolean>) => {
    if (!window.shiori) return;
    setBusy(true);
    setStoreError(null);
    try {
      if (await op(window.shiori)) await askStorage();
    } catch {
      setStoreError(failed);
      await askStorage();
    } finally {
      setBusy(false);
    }
  };
  const answer = (keep: boolean) => {
    const first = infoRef.current?.keep === null;
    return act("Could not save your answer.", async (api) => {
      await api.setKeepDocuments(keep);
      if (keep) {
        const listed = (await api.listDocuments()).documents;
        setDocs((all) => afterYes(all ?? [], listed, first));
      }
      return true;
    });
  };
  // main shows the confirm dialog; false means cancelled.
  const deleteOne = (docId: string) =>
    act("Could not delete this document.", async (api) => {
      if (!(await api.deleteDocument(docId))) return false;
      setDocs((all) => withoutDocs(all ?? [], [docId]));
      return true;
    });
  // Takes deleted documents off the screen. Results that were never saved stay open.
  const remove = (ids: string[]) => {
    setDocs((all) => withoutDocs(all ?? [], ids));
    setOpen((o) => (o && ids.includes(o.fx.doc_id) ? null : o));
  };
  const deleteAll = () =>
    act("Could not delete the saved documents.", async (api) => {
      try {
        if (!(await api.deleteAllDocuments())) return false;
      } catch (e) {
        // It may have stopped part way.
        const list = await api.listDocuments();
        remove(removedIds(docs ?? [], list, list.folders ? await api.getStorage() : null));
        throw e;
      }
      remove(savedIds(docs ?? []));
      return true;
    });
  const notes = [...storeNotes(info), ...(storeError ? [storeError] : [])];

  const name = open ? titleOf(open.fx) : null;
  return (
    <div className="app">
      <header className={`bar${navigator.userAgent.includes("Mac") ? " mac" : ""}`}>
        <span className="logo" aria-hidden>栞</span>
        <b className="brand">Shiori</b>
        <button className={`navlink${open ? "" : " on"}`} onClick={() => { setOpen(null); setAdding(null); setSetup(null); }}>Library</button>
        {window.shiori && <button className={`navlink${setup ? " on" : ""}`} onClick={() => void window.shiori?.listModels().then((l) => { setStage("models"); setSetup(l); })}>Models</button>}
        {open && <span className="docname" title={name?.ja ?? undefined}>{name?.en ?? name?.ja ?? "Document"}</span>}
        <span className="grow" />
        {open && <button className="btn" disabled title="Export is not available yet">Export</button>}
        <button className="btn sq" aria-label="Settings" aria-expanded={settings} onClick={() => { if (!settings) void askStorage(); setSettings(!settings); }}>⚙</button>
      </header>
      {settings && <Settings info={info} unread={unread} busy={busy} error={storeError} onKeep={(keep) => void answer(keep)} onDeleteAll={() => void deleteAll()} />}
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
      {showQuestion(finishedAny, info) && !(setup && stage !== "models") && (
        <div className="ask" role="region" aria-label="Saving">
          <span>{QUESTION}</span>
          <div className="rowactions">
            <button className="btn" disabled={busy} onClick={() => void answer(true)}>Yes</button>
            <button className="btn" disabled={busy} onClick={() => void answer(false)}>No</button>
          </div>
          {storeError && <span className="meta">{storeError}</span>}
        </div>
      )}
      <main>
        {!docs && <div className="err">Loading</div>}
        {setup && stage === "models" && <Setup list={setup} onRefresh={async () => setSetup((await window.shiori?.listModels()) ?? null)} onClose={() => setSetup(null)} onFind={() => setStage("find")} />}
        {setup && stage !== "models" && (
          <Onboarding list={setup} stage={stage} onStage={setStage} onRefresh={async () => setSetup((await window.shiori?.listModels()) ?? null)} onAdd={() => { setSetup(null); void add(); }} onClose={() => setSetup(null)} />
        )}
        {docs && !setup && adding && <Processing docId={adding.doc_id} name={adding.name} onDone={finished} onBack={() => setAdding(null)} />}
        {docs && !setup && !adding && !open && <Library docs={docs} onOpen={setOpen} onAdd={add} canAdd={!!window.shiori} notes={notes} empty={emptyText(info)} onDelete={(id) => void deleteOne(id)} busy={busy} />}
        {open && !setup && <Workspace fx={open.fx} counts={open.counts} />}
      </main>
    </div>
  );
}
