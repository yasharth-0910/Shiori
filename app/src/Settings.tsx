// The Settings popover (docs/storage_design.md section 3, D-123). What it shows is decided in saving.ts; main asks for
// the delete confirmation in a native dialog.
import { settingsState, UPDATE_NOTE } from "./saving";
import type { StorageInfo } from "./shiori.d.ts";

type Props = { info: StorageInfo | null; unread: boolean; busy: boolean; error: string | null; onKeep: (keep: boolean) => void; onDeleteAll: () => void };

export function Settings({ info, unread, busy, error, onKeep, onDeleteAll }: Props) {
  const s = settingsState(info, unread);
  return (
    <div className="pop" role="dialog" aria-label="Settings">
      <b>Settings</b>
      <label className="switch">
        <input type="checkbox" role="switch" checked={s.checked} disabled={s.switchDisabled || busy} onChange={(e) => onKeep(e.target.checked)} />
        <span>
          Keep documents in your Library between sessions
          <span className="meta">Encrypted on this computer.</span>
        </span>
      </label>
      {s.notes.map((n) => (
        <p key={n} className="pnotice" role="status">{n}</p>
      ))}
      {s.count && <p className="meta">{s.count}</p>}
      <button className="btn" disabled={s.deleteDisabled || busy} onClick={onDeleteAll}>
        Delete all saved documents
      </button>
      <p className="meta">{UPDATE_NOTE}</p>
      {error && <p className="meta" role="alert">{error}</p>}
    </div>
  );
}
