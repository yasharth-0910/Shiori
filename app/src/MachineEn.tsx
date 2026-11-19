import { MT_LABEL } from "./translate";

// The only place a model-written English line is drawn, so every one carries the label (D-85).
// big: the answer line of a card (larger); otherwise a smaller secondary line.
export function MachineEn({ text, note, big = false }: { text: string; note: string | null; big?: boolean }) {
  return (
    <div className={big ? "en big" : "en"}>
      <span className="entext">{text}</span> <span className="meta mt">{MT_LABEL}</span>
      {note && <span className="meta note"> · {note}</span>}
    </div>
  );
}
