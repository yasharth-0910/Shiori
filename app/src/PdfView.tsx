import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useRef, useState } from "react";
import type { Sentence } from "./types";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const SCALE = 1.4; // CSS px per PDF point

type PageInfo = { n: number; w: number; h: number };

export function PdfView({ url, active }: { url: string; active: Sentence | null }) {
  const [pages, setPages] = useState<PageInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const holder = useRef<HTMLDivElement>(null);
  const pdfRef = useRef<pdfjs.PDFDocumentProxy | null>(null);

  useEffect(() => {
    let dead = false;
    const task = pdfjs.getDocument({ url, cMapUrl: "./cmaps/", cMapPacked: true });
    task.promise
      .then(async (pdf) => {
        const infos: PageInfo[] = [];
        for (let n = 1; n <= pdf.numPages; n++) {
          const v = (await pdf.getPage(n)).getViewport({ scale: SCALE });
          infos.push({ n, w: v.width, h: v.height });
        }
        if (dead) return;
        setPages(infos);
        pdfRef.current = pdf;
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

  // Draw once the canvases are in the DOM, at device resolution.
  useEffect(() => {
    const pdf = pdfRef.current;
    if (!pdf) return;
    let dead = false;
    void (async () => {
      for (const { n } of pages) {
        const canvas = holder.current?.querySelector<HTMLCanvasElement>(`canvas[data-page="${n}"]`);
        if (!canvas || dead) return;
        const page = await pdf.getPage(n);
        const viewport = page.getViewport({ scale: SCALE * (window.devicePixelRatio || 1) });
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        await page.render({ canvas, viewport }).promise;
      }
    })().catch((e: unknown) => console.error("render", String(e)));
    return () => {
      dead = true;
    };
  }, [pages]);

  // Jump: scroll the first highlight box into the middle of the view.
  useEffect(() => {
    if (!active) return;
    holder.current?.querySelector(".hl")?.scrollIntoView({ block: "center", behavior: "instant" });
  }, [active, pages]);

  if (error) return <div className="err">PDF failed: {error}</div>;
  return (
    <div className="pdf" ref={holder}>
      {pages.map((p) => (
        <div key={p.n} className="page" data-page={p.n} style={{ width: p.w, height: p.h }}>
          <canvas data-page={p.n} style={{ width: p.w, height: p.h }} />
          {active?.boxes
            .filter((b) => b.page === p.n)
            .map((b, i) => (
              <div
                key={i}
                className="hl"
                style={{
                  left: b.bbox[0] * SCALE,
                  top: b.bbox[1] * SCALE,
                  width: (b.bbox[2] - b.bbox[0]) * SCALE,
                  height: (b.bbox[3] - b.bbox[1]) * SCALE,
                }}
              />
            ))}
        </div>
      ))}
    </div>
  );
}
