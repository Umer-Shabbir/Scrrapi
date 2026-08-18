// Shared helpers for the dev scripts. Node builtins only -- the root has
// nothing to install before any of this can run.
import { spawn } from "node:child_process";
import { createWriteStream, existsSync, mkdirSync } from "node:fs";
import { appendFile } from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..");
export const BACKEND = path.join(ROOT, "backend");
export const FRONTEND = path.join(ROOT, "frontend");
export const LOG_DIR = path.join(ROOT, "logs");

if (!existsSync(LOG_DIR)) mkdirSync(LOG_DIR, { recursive: true });

const COLORS = {
  db: "\x1b[36m", // cyan
  api: "\x1b[32m", // green
  worker: "\x1b[35m", // magenta
  ui: "\x1b[33m", // yellow
  dev: "\x1b[90m", // grey
  error: "\x1b[31m", // red
};
const RESET = "\x1b[0m";
const useColor = process.stdout.isTTY;

/** Short status line to the terminal. This is the ONLY thing meant to reach
 * the console during normal operation -- everything a child process prints
 * goes to logs/<label>.log instead. Keep these to one line each. */
export function status(label, msg) {
  const color = useColor ? COLORS[label] ?? "" : "";
  const reset = useColor ? RESET : "";
  process.stdout.write(`${color}[${label}]${reset} ${msg}\n`);
}

export function fail(label, msg) {
  const color = useColor ? COLORS.error : "";
  const reset = useColor ? RESET : "";
  process.stdout.write(`${color}[${label}] ${msg}${reset}\n`);
}

/** Run a child process with its stdout/stderr redirected entirely to a log
 * file, surfacing only a start/exit status line on the console. Returns the
 * child handle so the caller can track/kill it. */
export function runLogged(label, command, args, opts = {}) {
  const logPath = path.join(LOG_DIR, `${label}.log`);
  const out = createWriteStream(logPath, { flags: "a" });
  out.write(`\n----- ${new Date().toISOString()} :: ${command} ${args.join(" ")} -----\n`);

  const child = spawn(command, args, {
    cwd: opts.cwd ?? ROOT,
    env: { ...process.env, ...opts.env },
    shell: process.platform === "win32",
    stdio: ["ignore", "pipe", "pipe"],
  });

  child.stdout.pipe(out, { end: false });
  child.stderr.pipe(out, { end: false });

  child.on("exit", (code, signal) => {
    out.write(`\n----- exited code=${code} signal=${signal} -----\n`);
  });

  return { child, logPath };
}

/** Wait for a child's log file (or a readiness probe) instead of guessing a
 * fixed sleep. `probe` is polled every 500ms; give up after timeoutMs. */
export async function waitUntil(label, probe, { timeoutMs = 60_000, intervalMs = 500 } = {}) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await probe().catch(() => false)) return true;
    await sleep(intervalMs);
  }
  return false;
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** True if something is already listening on this TCP port -- used for the
 * "ports are strict" rule: refuse to start rather than silently rebind. */
// Checks both the literal loopback address and "localhost" -- on this host
// Vite's dev server answers only on whatever "localhost" resolves to (::1),
// not on 127.0.0.1 directly, so a check against just one address can miss a
// port that's actually taken.
export async function portInUse(port) {
  const tryHost = (host) =>
    new Promise((resolve) => {
      const socket = net.createConnection({ port, host });
      socket.once("connect", () => {
        socket.destroy();
        resolve(true);
      });
      socket.once("error", () => resolve(false));
    });
  return (await tryHost("127.0.0.1")) || (await tryHost("localhost"));
}

export async function httpOk(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

export async function appendSummary(line) {
  await appendFile(
    path.join(LOG_DIR, "dev.log"),
    `${new Date().toISOString()} ${line}\n`,
  );
}

export function hasFlag(argv, name) {
  return argv.includes(name);
}

export function venvPython() {
  return process.platform === "win32"
    ? path.join(BACKEND, ".venv", "Scripts", "python.exe")
    : path.join(BACKEND, ".venv", "bin", "python");
}

export function venvPip() {
  return process.platform === "win32"
    ? path.join(BACKEND, ".venv", "Scripts", "pip.exe")
    : path.join(BACKEND, ".venv", "bin", "pip");
}
