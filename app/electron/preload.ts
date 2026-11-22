// The whole bridge between the renderer and the main process: six functions (D-83, D-85, D-90, D-98).
// None takes a path, a URL or a token. The renderer asks; main picks the file, talks to
// the sidecar and answers. Sandboxed preload: only "electron" may be required here.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("shiori", {
  startProcessing: () => ipcRenderer.invoke("shiori:start"),
  getStatus: (docId: string, since?: number) => ipcRenderer.invoke("shiori:status", docId, since ?? 0),
  cancel: (docId: string) => ipcRenderer.invoke("shiori:cancel", docId),
  getFields: (docId: string) => ipcRenderer.invoke("shiori:fields", docId),
  translate: (docId: string, ids: string[]) => ipcRenderer.invoke("shiori:translate", docId, ids),
  saveExport: (kind: "csv" | "ics", name: string, content: string) => ipcRenderer.invoke("shiori:save", kind, name, content),
});
