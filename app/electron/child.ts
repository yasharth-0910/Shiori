// The one place the app starts a process (app/test/child.test.ts holds this). windowsHide stops a console window on
// Windows. A piped stderr is read to the end and only counted: a line can hold document text or a path, so none is
// kept or logged. Log lines hold the event name, the error type, the exit code or signal and the line count.
import { spawn, type ChildProcess, type SpawnOptions } from "node:child_process";
import { errorType, userFile } from "./userfile.ts";

export function startChild(name: string, command: string, args: string[], options: SpawnOptions, log: (line: string) => void = console.error): ChildProcess {
  // userFile: a synchronous spawn error is logged and thrown on as its type only (its message can hold a path).
  const p = userFile(`${name}_spawn`, () => spawn(command, args, { ...options, windowsHide: true }), log);
  let newlines = 0;
  let partial = false; // the last chunk did not end its line
  p.stderr?.on("data", (d: Buffer) => {
    for (const byte of d) if (byte === 10) newlines++;
    partial = d[d.length - 1] !== 10;
  });
  p.stderr?.on("error", (e) => log(`${name}_stderr failed: ${errorType(e)}`));
  p.on("error", (e) => log(`${name}_process failed: ${errorType(e)}`));
  // "close", not "exit": it comes after the last of stderr has been read.
  p.on("close", (code, signal) => {
    const lines = p.stderr ? ` stderr_lines=${newlines + Number(partial)}` : "";
    log(`${name}_closed: code=${code} signal=${signal}${lines}`);
  });
  return p;
}
