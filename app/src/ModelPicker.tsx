// Model choice in the Add document flow (D-99). Plain HTML only: a <details> dropdown of radio rows, and an "i" button
// per row whose card shows on hover or keyboard focus (CSS :hover / :focus-within, no script, no external font).
import { infoRows, optionLabel } from "./modelinfo";
import type { ModelList } from "./shiori.d.ts";

type Props = { list: ModelList; value: string | null; onChange: (id: string) => void };

export function ModelPicker({ list, value, onChange }: Props) {
  const chosen = list.models.find((m) => m.id === value);
  const anyInstalled = list.models.some((m) => m.installed);
  return (
    <div className="mpicker">
      <span className="meta" id="mp-label">Model</span>
      <details className="mdrop">
        <summary aria-labelledby="mp-label">{chosen ? optionLabel(chosen) : "No model installed"}</summary>
        <ul className="mlist" role="radiogroup" aria-labelledby="mp-label">
          {list.models.map((m) => (
            <li key={m.id} className="mrow">
              <label className={m.installed ? "" : "off"}>
                <input type="radio" name="model" value={m.id} checked={m.id === value} disabled={!m.installed} onChange={() => onChange(m.id)} />
                <span>{optionLabel(m)}</span>
                {list.recommended?.id === m.id && <span className="pill mrec">Recommended</span>}
              </label>
              <span className="infowrap">
                <button type="button" className="infobtn" aria-label={`About ${m.name}`} aria-describedby={`mi-${m.id}`}>i</button>
                <span className="infocard" role="tooltip" id={`mi-${m.id}`}>
                  <dl>
                    {infoRows(m).map(([k, v]) => (
                      <div key={k}>
                        <dt>{k}</dt>
                        <dd>{v}</dd>
                      </div>
                    ))}
                  </dl>
                </span>
              </span>
            </li>
          ))}
        </ul>
      </details>
      {list.recommended && <p className="meta">Recommended for this machine: {list.recommended.reason}</p>}
      {!anyInstalled && (
        <div className="pnotice" role="status">
          <b>Model not set up.</b> {list.binaryFound ? "" : "llama-server was not found (set SHIORI_LLAMA_SERVER or put it on PATH). "}
          Expected files:
          <ul>
            {list.expected.map((x) => (
              <li key={x.file} className="mono">{x.file} <span className="meta">in {x.where}</span></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
