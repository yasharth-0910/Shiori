// The whole bridge between the renderer and the main process: eleven functions (D-83, D-85, D-90, D-98, D-99, D-100).
// None takes a path, a URL or a token (download takes a registry id). The renderer asks; main picks the file, talks to
// the sidecar and answers. Sandboxed preload: only "electron" may be required here.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("shiori", {
  startProcessing: (modelId?: string) => ipcRenderer.invoke("shiori:start", modelId),
  listModels: () => ipcRenderer.invoke("shiori:models"),
  getStatus: (docId: string, since?: number) => ipcRenderer.invoke("shiori:status", docId, since ?? 0),
  cancel: (docId: string) => ipcRenderer.invoke("shiori:cancel", docId),
  getFields: (docId: string) => ipcRenderer.invoke("shiori:fields", docId),
  translate: (docId: string, ids: string[]) => ipcRenderer.invoke("shiori:translate", docId, ids),
  saveExport: (kind: "csv" | "ics", name: string, content: string) => ipcRenderer.invoke("shiori:save", kind, name, content),
  openCalendar: () => ipcRenderer.invoke("shiori:open-calendar"),
  downloadModel: (modelId: string) => ipcRenderer.invoke("shiori:download", modelId),
  downloadStatus: () => ipcRenderer.invoke("shiori:download-status"),
  chooseModelFile: () => ipcRenderer.invoke("shiori:import-model"),
});
