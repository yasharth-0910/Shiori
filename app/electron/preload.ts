// The whole bridge between the renderer and the main process: three functions (D-83).
// None takes a path, a URL or a token. The renderer asks; main picks the file, talks to
// the sidecar and answers. Sandboxed preload: only "electron" may be required here.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("shiori", {
  startProcessing: () => ipcRenderer.invoke("shiori:start"),
  getStatus: (docId: string) => ipcRenderer.invoke("shiori:status", docId),
  getFields: (docId: string) => ipcRenderer.invoke("shiori:fields", docId),
});
