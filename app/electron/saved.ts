// "Open in Calendar" (D-98): main remembers the one path the save dialog returned for the .ics and opens only that,
// with the operating system's default app. The renderer never passes a path. Pure so a test can drive it.
export function savedCalendar(open: (file: string) => Promise<string>) {
  let last: string | null = null;
  return {
    // Called by the save handler with the path it wrote. Only a .ics is kept (a typed name could end in .app or .exe).
    remember(file: string, kind: string): void {
      last = kind === "ics" && /\.ics$/i.test(file) ? file : null;
    },
    // electron's shell.openPath resolves to "" on success, else an error text.
    async openLast(): Promise<boolean> {
      if (!last) return false;
      return (await open(last)) === "";
    },
  };
}
