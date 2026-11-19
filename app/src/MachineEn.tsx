import { MT_LABEL } from "./translate";

// The only place an English line is drawn, so every one carries the label (D-85).
export function MachineEn({ text, note }: { text: string; note: string | null }) {
  return (
    <div className="en">
      {text} <span className="meta">{MT_LABEL}</span>
      {note && <span className="meta"> · {note}</span>}
    </div>
  );
}
