// Setup and model download (D-100). The one screen where the app may use the internet, and only after a click on
// Download. It never sees a URL to fetch: it sends the registry id, and main downloads that entry's pinned URL.
import { useEffect, useState } from "react";
import { InfoCard } from "./ModelPicker";
import type { DownloadError, ImportResult, ModelInfo, ModelList } from "./shiori.d.ts";

type Props = { list: ModelList; onRefresh: () => Promise<void>; onClose: () => void; onFind: () => void };

const ERRORS: Record<DownloadError, string> = {
  offline: "No internet connection. Try again when you are online, or choose a model file from disk.",
  interrupted: "The download stopped. Click Download to carry on where it left off.",
  http_error: "The download server did not answer as expected. Nothing was installed.",
  hash_mismatch: "The file did not match the expected SHA-256, so it was deleted. Nothing was installed.",
  disk: "Shiori could not save the file. Check that the disk has room.",
};
const IMPORT_ERRORS: Record<Exclude<ImportResult, { ok: true }>["reason"], string> = {
  not_gguf: "That is not a .gguf file. Nothing was copied.",
  unknown_file: "That file does not match any model Shiori knows (its SHA-256 is different). Nothing was copied.",
  disk: "Shiori could not copy the file. Check that the disk has room.",
};

const sizeText = (bytes: number) => `${(bytes / 1e9).toFixed(2)} GB`;
const host = (url: string) => {
  try {
    return new URL(url).host;
  } catch {
    return "";
  }
};

export function Setup({ list, onRefresh, onClose, onFind }: Props) {
  const [dl, setDl] = useState<Awaited<ReturnType<NonNullable<typeof window.shiori>["downloadStatus"]>> | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const bridge = window.shiori;
  const anyInstalled = list.models.some((m) => m.installed);
  const active = dl && (dl.phase === "downloading" || dl.phase === "verifying");

  // Poll while a download runs (and once on open, in case one is already running).
  useEffect(() => {
    let live = true;
    const tick = async () => {
      const s = await bridge?.downloadStatus();
      if (!live || !s) return;
      setDl(s);
      if (s.phase === "done") await onRefresh();
    };
    void tick();
    const t = setInterval(() => void tick(), 500);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [bridge, onRefresh]);

  const download = async (m: ModelInfo) => {
    setNote(null);
    try {
      await bridge?.downloadModel(m.id);
    } catch {
      setNote("Could not start the download.");
    }
  };
  const choose = async () => {
    setNote(null);
    const r = await bridge?.chooseModelFile();
    if (!r) return;
    if (r.ok) await onRefresh();
    else setNote(IMPORT_ERRORS[r.reason]);
  };

  return (
    <section className="setup" aria-label="Set up a model">
      <h2>Set up a model</h2>
      <p>Shiori reads tenders with a language model that runs on this computer. Pick one to download once.</p>
      <p className="pnotice" role="note"><b>The only network use is downloading a model, which you start yourself and which sends none of your documents.</b></p>
      <ul className="mcards">
        {list.models.map((m) => {
          const mine = dl?.id === m.id;
          return (
            <li key={m.id} className="mcard">
              <div className="mhead">
                <b>{m.name}</b>
                {list.recommended?.id === m.id && <span className="pill mrec">Recommended</span>}
                {m.installed && <span className="pill pill-verified">Installed</span>}
                <span className="grow" />
                <InfoCard m={m} />
              </div>
              <dl className="mfacts">
                <div><dt>Size</dt><dd>{sizeText(m.sizeBytes)}</dd></div>
                {m.url && <div><dt>Downloads from</dt><dd>{host(m.url)} <span className="meta">(it may pass you to its own download servers, over https)</span></dd></div>}
                <div><dt>SHA-256</dt><dd className="mono hash">{m.sha256}</dd></div>
              </dl>
              {!m.installed && !m.url && <p className="meta">Download not available yet.</p>}
              {!m.installed && m.url && !(mine && active) && (
                <div className="drow l">
                  <button className="btn primary" disabled={!!active} onClick={() => void download(m)}>
                    {mine && dl?.phase === "failed" && dl.error === "interrupted" ? "Resume download" : "Download"}
                  </button>
                </div>
              )}
              {mine && active && dl && (
                <div role="status">
                  <progress max={dl.total || 1} value={dl.phase === "verifying" ? undefined : dl.received} aria-label={`Downloading ${m.name}`} />
                  <p className="meta">
                    {dl.phase === "verifying" ? "Checking the file (SHA-256)" : `${sizeText(dl.received)} of ${sizeText(dl.total)}`}
                  </p>
                </div>
              )}
              {mine && dl?.phase === "failed" && dl.error && <p className="err">{ERRORS[dl.error]}</p>}
            </li>
          );
        })}
      </ul>
      {note && <p className="err">{note}</p>}
      <div className="drow l">
        <button className="btn" disabled={!!active} onClick={() => void choose()}>Choose a model file from disk</button>
        <button className="btn" disabled={!!active} onClick={onFind}>Find models on this computer</button>
        <span className="grow" />
        <button className="btn" onClick={onClose}>{anyInstalled ? "Done" : "Skip for now"}</button>
      </div>
      <p className="meta">A file from disk is only used if its SHA-256 matches one of the models above.</p>
    </section>
  );
}
