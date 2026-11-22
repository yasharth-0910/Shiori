// The renderer's request filter (D-100). Only the app's own scheme (shiori://), devtools, data: and blob: pass;
// every other request from a page is cancelled, including to 127.0.0.1 and localhost (the renderer never needs them:
// main talks to the sidecar). Cancelled requests are counted, never listed. The model download runs in main-process
// code (download.ts), which this session filter does not see.
const OK = /^(shiori|devtools|data|blob):/;

export const allowRequest = (url: string): boolean => OK.test(url);

export function requestFilter() {
  let blocked = 0;
  return {
    // Shape of electron's webRequest.onBeforeRequest listener.
    onBeforeRequest(d: { url: string }, cb: (r: { cancel: boolean }) => void): void {
      const cancel = !allowRequest(d.url);
      if (cancel) blocked++;
      cb({ cancel });
    },
    blockedCount: (): number => blocked,
  };
}
