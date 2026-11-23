import { useEffect, useMemo, useRef } from "react";
import type { Find } from "./PdfView";
import { codepoints, findAll, paragraphs, slices, type Mark, type Range } from "./textmath";

// The text of an HTML notice, as plain text paragraphs. Only text nodes are rendered: nothing from the page is parsed
// as HTML, so nothing in it can run, load an image, font or script, or fetch anything. The highlight is the exact
// character range the sidecar stored for the cited sentence (D-37).
export function TextView(props: { text: string; enSummary: Range | null; active: Range | null; find: Find | null; onFindCount: (n: number) => void }) {
  const { text, enSummary, active, find, onFindCount } = props;
  const holder = useRef<HTMLDivElement>(null);
  const cps = useMemo(() => codepoints(text), [text]);
  const paras = useMemo(() => paragraphs(cps), [cps]);
  const hits = useMemo(() => (find ? findAll(cps, find.q) : []), [cps, find?.q]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => onFindCount(hits.length), [hits.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const cur = hits.length ? (find?.step ?? 0) % hits.length : -1;
  const marks: Mark[] = [
    ...hits.map((h, i): Mark => ({ ...h, kind: i === cur ? "cur" : "hit" })),
    ...(active ? [{ ...active, kind: "hl" as const }] : []),
  ];

  useEffect(() => {
    if (active) holder.current?.querySelector(".thl")?.scrollIntoView({ block: "center", behavior: "instant" });
  }, [active?.start, active?.end]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (cur >= 0) holder.current?.querySelector(".thit.cur")?.scrollIntoView({ block: "center", behavior: "instant" });
  }, [cur, hits]);

  const para = (p: Range) => (
    <p key={p.start} className="tp" data-start={p.start} data-end={p.end} lang="ja">
      {slices(cps, p, marks).map((s) => {
        const kind = s.kinds.includes("hl") ? "thl" : s.kinds.includes("cur") ? "thit cur" : s.kinds.includes("hit") ? "thit" : "";
        return kind ? (
          <span key={s.start} className={kind} data-start={s.start} data-end={s.end}>{s.text}</span>
        ) : (
          s.text
        );
      })}
    </p>
  );
  const inSummary = (p: Range) => !!enSummary && p.start >= enSummary.start && p.end <= enSummary.end;
  const body = paras.filter((p) => !inSummary(p));
  const summary = paras.filter(inSummary);
  const firstSummary = summary[0]?.start ?? Infinity;
  return (
    <div className="pdfpane">
      <div className="pdfbar">
        <span className="meta">Text of the saved page. Shiori shows the extracted text, not the web page.</span>
      </div>
      <div className="textscroll" ref={holder}>
        <div className="textdoc">
          {text === "" && <p className="empty">This page has no readable text.</p>}
          {body.filter((p) => p.start < firstSummary).map(para)}
          {summary.length > 0 && (
            <section className="ensum" lang="en">
              <div className="ensumlabel">English Summary. This is the page&rsquo;s own text, not Shiori&rsquo;s translation.</div>
              {summary.map(para)}
            </section>
          )}
          {body.filter((p) => p.start >= firstSummary).map(para)}
        </div>
      </div>
    </div>
  );
}
