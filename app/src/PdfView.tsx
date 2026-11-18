import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useRef, useState } from "react";
import type { Box, Sentence } from "./types";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const BASE = 1.4; // CSS px per PDF point at 100%
const STEPS = [50, 75, 100, 125, 150, 200];

type PageInfo = { n: number; w: number; h: number }; // PDF points
type PageText = { text: string; owner: number[]; boxes: Box["bbox"][] };
export type Find = { q: string; step: number };

// NFKC per character so full-width digits and letters match what a person types.
const fold = (s: string) => s.normalize("NFKC").toLowerCase();

export function PdfView(props: {
  url: string;
  active: Sentence | null;
  find: Find | null;
  onFindCount: (n: number) => void;
}) {
  const { url, active, find, onFindCount } = props;
  const [pages, setPages] = useState<PageInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [cur, setCur] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [hits, setHits] = useState<{ page: number; boxes: Box["bbox"][] }[]>([]);
  const holder = useRef<HTMLDivElement>(null);
  const pdfRef = useRef<pdfjs.PDFDocumentProxy | null>(null);
  const texts = useRef(new Map<number, PageText>());
  const scale = (BASE * zoom) / 100;

  useEffect(() => {
    let dead = false;
    const task = pdfjs.getDocument({ url, cMapUrl: "./cmaps/", cMapPacked: true });
    task.promise
      .then(async (pdf) => {
        const infos: PageInfo[] = [];
        for (let n = 1; n <= pdf.numPages; n++) {
          const v = (await pdf.getPage(n)).getViewport({ scale: 1 });
          infos.push({ n, w: v.width, h: v.height });
        }
        if (dead) return;
        pdfRef.current = pdf;
        texts.current.clear();
        setPages(infos);
      })
      .catch((e: unknown) => {
        console.error(String(e));
        setError(String(e));
      });
    return () => {
      dead = true;
      void task.destroy();
    };
  }, [url]);

  // Draw once the canvases are in the DOM, at device resolution. A zoom change cancels the pass in flight.
  useEffect(() => {
    const pdf = pdfRef.current;
    if (!pdf) return;
    let dead = false;
    let task: pdfjs.RenderTask | null = null;
    void (async () => {
      for (const { n } of pages) {
        const canvas = holder.current?.querySelector<HTMLCanvasElement>(`canvas[data-page="${n}"]`);
        if (!canvas || dead) return;
        const page = await pdf.getPage(n);
        const viewport = page.getViewport({ scale: scale * (window.devicePixelRatio || 1) });
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        task = page.render({ canvas, viewport });
        await task.promise;
      }
    })().catch((e: unknown) => {
      if ((e as { name?: string }).name !== "RenderingCancelledException") console.error("render", String(e));
    });
    return () => {
      dead = true;
      task?.cancel();
    };
  }, [pages, scale]);

  const goPage = (n: number) => {
    const el = holder.current?.querySelector<HTMLElement>(`.page[data-page="${n}"]`);
    if (el && holder.current) holder.current.scrollTo({ top: el.offsetTop - 12, behavior: "instant" });
  };

  // Jump to the cited sentence.
  useEffect(() => {
    if (active) holder.current?.querySelector(".hl")?.scrollIntoView({ block: "center", behavior: "instant" });
  }, [active, pages, scale]);

  // Search: text of every page once, then match on folded text; each match keeps the boxes of the text runs it covers.
  useEffect(() => {
    const pdf = pdfRef.current;
    const q = find ? fold(find.q.trim()) : "";
    if (!pdf || !q) {
      setHits([]);
      onFindCount(0);
      return;
    }
    let dead = false;
    void (async () => {
      const found: { page: number; boxes: Box["bbox"][] }[] = [];
      for (const { n } of pages) {
        let pt = texts.current.get(n);
        if (!pt) {
          const page = await pdf.getPage(n);
          const vp = page.getViewport({ scale: 1 });
          const content = await page.getTextContent();
          pt = { text: "", owner: [], boxes: [] };
          for (const it of content.items) {
            if (!("str" in it)) continue;
            const [, , , , e, f] = it.transform as number[];
            // ponytail: unrotated pages only; PDF y runs up, the viewer's runs down.
            pt.boxes.push([e!, vp.height - f! - it.height, e! + it.width, vp.height - f! + it.height * 0.2]);
            for (const ch of it.str) {
              const g = fold(ch);
              pt.text += g;
              for (let k = 0; k < g.length; k++) pt.owner.push(pt.boxes.length - 1);
            }
          }
          texts.current.set(n, pt);
        }
        for (let at = pt.text.indexOf(q); at >= 0; at = pt.text.indexOf(q, at + q.length)) {
          const ids = new Set(pt.owner.slice(at, at + q.length));
          found.push({ page: n, boxes: [...ids].map((i) => pt.boxes[i]!) });
        }
      }
      if (dead) return;
      setHits(found);
      onFindCount(found.length);
    })().catch((e: unknown) => console.error("find", String(e)));
    return () => {
      dead = true;
    };
    // onFindCount is a state setter from the parent; the search reruns only for a new query.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [find?.q, pages, url]);

  const hitNo = hits.length ? (find?.step ?? 0) % hits.length : -1;
  useEffect(() => {
    if (hitNo >= 0) holder.current?.querySelector(".hit.cur")?.scrollIntoView({ block: "center", behavior: "instant" });
  }, [hitNo, hits, scale]);

  const onScroll = () => {
    const h = holder.current;
    if (!h) return;
    let n = 1;
    for (const el of h.querySelectorAll<HTMLElement>(".page")) {
      if (el.offsetTop - h.scrollTop <= h.clientHeight * 0.35) n = Number(el.dataset.page);
    }
    setCur(n);
    setPageInput(String(n));
  };

  const box = (b: Box["bbox"]) => ({
    left: b[0] * scale,
    top: b[1] * scale,
    width: (b[2] - b[0]) * scale,
    height: (b[3] - b[1]) * scale,
  });
  const total = pages.length;
  const commitPage = () => {
    const n = Math.min(Math.max(Number(pageInput) || cur, 1), total);
    setPageInput(String(n));
    goPage(n);
  };
  const stepZoom = (dir: 1 | -1) => {
    const i = STEPS.indexOf(zoom);
    setZoom(STEPS[Math.min(Math.max(i + dir, 0), STEPS.length - 1)] ?? 100);
  };

  if (error) return <div className="err">PDF failed: {error}</div>;
  return (
    <div className="pdfpane">
      <div className="pdfbar">
        <button className="btn sq" aria-label="Previous page" disabled={cur <= 1} onClick={() => goPage(cur - 1)}>‹</button>
        <span className="pageno">
          Page{" "}
          <input
            aria-label="Page number"
            value={pageInput}
            onChange={(e) => setPageInput(e.target.value)}
            onBlur={commitPage}
            onKeyDown={(e) => e.key === "Enter" && commitPage()}
          />{" "}
          of {total}
        </span>
        <button className="btn sq" aria-label="Next page" disabled={cur >= total} onClick={() => goPage(cur + 1)}>›</button>
        <span className="grow" />
        <button className="btn sq" aria-label="Zoom out" disabled={zoom === STEPS[0]} onClick={() => stepZoom(-1)}>−</button>
        <span className="zoomno">{zoom}%</span>
        <button className="btn sq" aria-label="Zoom in" disabled={zoom === STEPS[STEPS.length - 1]} onClick={() => stepZoom(1)}>+</button>
      </div>
      <div className="pdf" ref={holder} onScroll={onScroll}>
        {pages.map((p) => (
          <div key={p.n} className="page" data-page={p.n} style={{ width: p.w * scale, height: p.h * scale }}>
            <canvas data-page={p.n} style={{ width: p.w * scale, height: p.h * scale }} />
            {hits.flatMap((h, hi) =>
              h.page === p.n ? h.boxes.map((b, i) => <div key={`${hi}-${i}`} className={`hit${hi === hitNo ? " cur" : ""}`} style={box(b)} />) : [],
            )}
            {active?.boxes.filter((b) => b.page === p.n).map((b, i) => <div key={i} className="hl" style={box(b.bbox)} />)}
          </div>
        ))}
      </div>
    </div>
  );
}
