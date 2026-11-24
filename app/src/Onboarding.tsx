// First-run onboarding (D-115): what Shiori does, find a model, ready. The scan starts only on a click and only reads
// files on this computer. The screen never has a path to send back: "Use this one" sends the index of a match.
import { useEffect, useState } from "react";
import { copyNotice, othersText, PRIVACY_TEXT, type Stage } from "./firstrun";
import type { ModelList, ScanState, UseResult } from "./shiori.d.ts";

type Props = {
  list: ModelList;
  stage: Exclude<Stage, "models">;
  onStage: (s: Stage) => void;
  onRefresh: () => Promise<void>;
  onAdd: () => void;
  onClose: () => void;
};

const gb = (bytes: number) => `${(bytes / 1e9).toFixed(2)} GB`;
const USE_ERRORS: Record<Exclude<UseResult, { ok: true }>["reason"], string> = {
  not_gguf: "That is not a .gguf file. Nothing was copied.",
  unknown_file: "That file did not match a model Shiori knows. Nothing was copied.",
  disk: "Shiori could not copy the file. Check that the disk has room.",
  gone: "That file is no longer there. Scan again.",
};

export function Onboarding({ list, stage, onStage, onRefresh, onAdd, onClose }: Props) {
  if (stage === "intro") {
    return (
      <section className="fr" aria-labelledby="fr-h">
        <p className="fr-label">First run</p>
        <h2 id="fr-h" className="fr-title">Welcome to Shiori</h2>
        <p className="fr-lead">Shiori reads Japanese public tender documents and gives you an English summary and the key facts, such as the deadline and who may bid. Every fact points to the sentence it came from.</p>
        <blockquote className="fr-note">
          <p className="fr-note-title">A note on your privacy</p>
          <p>{PRIVACY_TEXT}</p>
        </blockquote>
        <hr className="fr-rule" />
        <div className="fr-foot">
          <span className="fr-cap">All files stay on this machine</span>
          <button className="btn primary" onClick={() => onStage("find")}>Continue</button>
        </div>
      </section>
    );
  }
  if (stage === "ready") {
    const mine = list.models.filter((m) => m.installed);
    return (
      <section className="fr" aria-labelledby="fr-h">
        <p className="fr-label">All set</p>
        <h2 id="fr-h" className="fr-title">Ready</h2>
        {mine.length ? <p className="fr-lead">Model set up: <b>{mine.map((m) => m.name).join(", ")}</b></p> : <p className="fr-lead">No model is set up yet.</p>}
        <hr className="fr-rule" />
        <div className="fr-foot">
          <button className="fr-quiet" onClick={onClose}>Not now</button>
          <button className="btn primary" disabled={!mine.length} onClick={onAdd}>Add a PDF</button>
        </div>
      </section>
    );
  }
  return <Find list={list} onStage={onStage} onRefresh={onRefresh} onClose={onClose} />;
}

function Find({ list, onStage, onRefresh, onClose }: Pick<Props, "list" | "onStage" | "onRefresh" | "onClose">) {
  const bridge = window.shiori;
  const [scan, setScan] = useState<ScanState | null>(null);
  const [asked, setAsked] = useState(false); // a scan was started from this screen (or one was already running)
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const scanning = scan?.phase === "scanning";

  // One look when the screen opens, in case a scan is already running. A finished scan from before is not shown.
  useEffect(() => {
    void bridge?.scanStatus().then((s) => {
      if (s.phase === "scanning") {
        setScan(s);
        setAsked(true);
      }
    });
  }, [bridge]);
  useEffect(() => {
    if (!scanning) return;
    const t = setInterval(() => void bridge?.scanStatus().then(setScan), 400);
    return () => clearInterval(t);
  }, [bridge, scanning]);

  const start = async (kind: "computer" | "folder") => {
    setNote(null);
    setConfirm(null);
    try {
      if (!(await bridge?.scanModels(kind))) return; // the folder dialog was cancelled
    } catch {
      return setNote("Could not start the scan.");
    }
    setAsked(true);
    setScan(await bridge!.scanStatus());
  };
  const use = async (index: number) => {
    setBusy(true);
    setNote(null);
    const r = await bridge?.useScanned(index);
    setBusy(false);
    setConfirm(null);
    if (!r) return;
    if (r.ok) {
      await onRefresh();
      onStage("ready");
    } else setNote(USE_ERRORS[r.reason]);
  };

  const done = asked && scan && (scan.phase === "done" || scan.phase === "cancelled");
  const h = scan?.hashing;
  return (
    <section className="fr" aria-labelledby="fr-h">
      <p className="fr-label">Step 2 of 2</p>
      <h2 id="fr-h" className="fr-title">Find a model</h2>
      <p className="fr-lead">Shiori needs a language model that runs on this computer. If you already have one of the models it supports, it can find it.</p>
      <div className="fr-actions">
        <button className="btn primary" disabled={scanning || busy} onClick={() => void start("computer")}>Scan this computer for models</button>
        <button className="btn" disabled={scanning || busy} onClick={() => void start("folder")}>Search a folder...</button>
      </div>
      <p className="fr-small">
        The scan looks only in Shiori's own models folder, <code>~/.cache/huggingface/hub</code>, <code>~/.lmstudio/models</code> and <code>~/.ollama/models</code> (the same folders under your user profile on Windows). It does not look in Downloads, Documents or Desktop. It checks each model file's size, then its SHA-256, and lists only exact matches. Nothing leaves this computer.
      </p>
      {scanning && scan && (
        <div className="fr-block" role="status">
          <p className="fr-small">Looked in {scan.folders} folders.</p>
          {h && (
            <>
              <progress max={h.sizeBytes || 1} value={h.doneBytes} aria-label="Checking a model file" />
              <p className="fr-small">Checking a {gb(h.sizeBytes)} file ({Math.floor((h.doneBytes / (h.sizeBytes || 1)) * 100)}%)</p>
            </>
          )}
          <div className="fr-actions"><button className="btn" onClick={() => void bridge?.scanCancel()}>Cancel</button></div>
        </div>
      )}
      {done && scan.phase === "cancelled" && <p className="fr-small">The scan was cancelled.</p>}
      {done && scan.phase === "done" && (
        <div className="fr-block" role="status">
          {scan.matches.length === 0 ? (
            <p className="fr-found">No supported model was found. You can search a folder or download one.</p>
          ) : (
            <ul className="fr-list">
              {scan.matches.map((m) => {
                const set = list.models.some((x) => x.id === m.id && x.installed);
                const n = copyNotice(m.sizeBytes, scan.freeBytes);
                return (
                  <li key={m.index} className="fr-item">
                    <div className="fr-itemhead"><b>{m.name}</b> <span className="fr-small">{gb(m.sizeBytes)}</span></div>
                    <p className="fr-small fr-path">{m.folder}</p>
                    {set && <p className="fr-small">Already set up.</p>}
                    {!set && confirm !== m.index && <div className="fr-actions"><button className="btn primary" disabled={busy} onClick={() => setConfirm(m.index)}>Use this one</button></div>}
                    {!set && confirm === m.index && (
                      <div>
                        <p className={n.enough ? "fr-small" : "fr-bad"}>{n.text}</p>
                        {busy ? <p className="fr-small" role="status">Copying and checking the file. This can take a minute.</p> : (
                          <div className="fr-actions">
                            <button className="btn primary" disabled={!n.enough} onClick={() => void use(m.index)}>Copy and use</button>
                            <button className="btn" onClick={() => setConfirm(null)}>Cancel</button>
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {scan.others > 0 && <p className="fr-small">{othersText(scan.others)}</p>}
        </div>
      )}
      {note && <p className="fr-bad">{note}</p>}
      <hr className="fr-rule" />
      <div className="fr-foot">
        <button className="fr-link" disabled={scanning || busy} onClick={() => onStage("models")}>Download a model</button>
        <button className="fr-quiet" onClick={onClose}>{list.models.some((m) => m.installed) ? "Done" : "Skip for now"}</button>
      </div>
    </section>
  );
}
