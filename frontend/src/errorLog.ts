// Ring buffer of the last 3 console.error calls, backing the 500 screen's
// "LAST 3 CONSOLE ERRORS" disclosure (SCREENLIST.md §23). Nothing in this
// app intercepted console.error before this -- installed once, at module
// load, by importing this file from main.tsx before anything else can log.
//
// Wraps the real console.error rather than replacing it: every call still
// reaches the browser devtools console unchanged, this just also remembers
// the last 3 formatted messages so a crash screen rendered *after* the
// error that caused it can still show what led up to it.

const MAX_ENTRIES = 3;
const buffer: string[] = [];

function formatArg(arg: unknown): string {
  if (arg instanceof Error) return `${arg.name}: ${arg.message}`;
  if (typeof arg === "string") return arg;
  try {
    return JSON.stringify(arg);
  } catch {
    return String(arg);
  }
}

const originalConsoleError = console.error.bind(console);

console.error = (...args: unknown[]) => {
  const message = args.map(formatArg).join(" ");
  buffer.push(message);
  if (buffer.length > MAX_ENTRIES) buffer.shift();
  originalConsoleError(...args);
};

window.addEventListener("error", (event) => {
  const message = event.error instanceof Error
    ? `${event.error.name}: ${event.error.message}`
    : event.message;
  buffer.push(message);
  if (buffer.length > MAX_ENTRIES) buffer.shift();
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  const message = reason instanceof Error ? `${reason.name}: ${reason.message}` : String(reason);
  buffer.push(`Unhandled rejection: ${message}`);
  if (buffer.length > MAX_ENTRIES) buffer.shift();
});

/** Snapshot of the last (up to 3) console errors, oldest first. */
export function recentConsoleErrors(): string[] {
  return [...buffer];
}

/** A short id to quote in a bug report -- not a server-correlated request id
 * (nothing in this app generates/logs one), just a random, roughly-unique
 * token so two crash reports can be told apart in conversation. */
export function newErrorId(): string {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return `ERR_${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
}
