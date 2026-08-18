#!/usr/bin/env node
// One command brings up infra, API, Celery worker and the UI -- see README.md.
//
// Terminal output is deliberately thin: one status line per step. Everything a
// child process prints (pip, alembic, uvicorn, celery, vite) goes to
// logs/<name>.log instead -- full JSON/text logs live there, not the console.
// This is what stops a busy worker's per-request logging from flooding (and
// once, crashing) the terminal -- see backend/app/core/logging.py's own note
// on that. The Dashboard's live log panel (SystemLogPanel / /api/system/events
// stream) is the other place logs surface; this file's job is only to get the
// four processes running.
import { existsSync, copyFileSync, readFileSync, appendFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import {
  ROOT,
  BACKEND,
  FRONTEND,
  LOG_DIR,
  status,
  fail,
  runLogged,
  waitUntil,
  portInUse,
  httpOk,
  hasFlag,
  venvPython,
  venvPip,
  appendSummary,
} from "./lib.mjs";

const argv = process.argv.slice(2);
const noDocker = hasFlag(argv, "--no-docker");
const noWorker = hasFlag(argv, "--no-worker");
const noOpen = hasFlag(argv, "--no-open");
const skipInstall = hasFlag(argv, "--skip-install");
const setupOnly = hasFlag(argv, "--setup-only");
const createUser = hasFlag(argv, "--create-user");

const children = [];
let shuttingDown = false;

function trackChild(label, handle) {
  children.push({ label, ...handle });
  return handle;
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  status("dev", "stopping...");
  for (const { child } of children) {
    if (child.killed || child.exitCode !== null) continue;
    try {
      if (process.platform === "win32") {
        // runLogged spawns through cmd.exe (shell:true) on Windows, so
        // child.kill() only kills the cmd.exe wrapper and leaves the real
        // uvicorn/celery/vite process (and any of *its* children, e.g. a
        // worker's Chromium) running as an orphan. /T kills the whole tree.
        spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        child.kill("SIGTERM");
      }
    } catch {
      // already gone
    }
  }
  process.exitCode = code;
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

async function main() {
  await step1_env();
  const ports = readPorts();
  await checkPortsStrict(ports);

  if (!noDocker) {
    await step2_infra();
  } else {
    status("db", "skipped (--no-docker) -- assuming Postgres/Redis are already reachable");
  }

  if (!skipInstall) {
    await step3_backendInstall();
    await step4_frontendInstall();
  } else {
    status("dev", "install skipped (--skip-install)");
  }

  await step5_migrate();

  if (createUser) {
    await runCreateUser(argv.slice(argv.indexOf("--create-user") + 1));
    return;
  }

  await step6_devUser();

  if (setupOnly) {
    status("dev", "setup complete (--setup-only) -- exiting");
    return;
  }

  await step7_start(ports);
}

// 1. backend/.env from .env.example, if missing.
async function step1_env() {
  const envPath = path.join(BACKEND, ".env");
  const examplePath = path.join(BACKEND, ".env.example");
  if (!existsSync(envPath)) {
    copyFileSync(examplePath, envPath);
    status("dev", "wrote backend/.env from .env.example");
  }
}

function readPorts() {
  const env = parseEnvFile(path.join(BACKEND, ".env"));
  return {
    api: Number(process.env.API_PORT || env.API_PORT || 8000),
    ui: Number(process.env.UI_PORT || env.UI_PORT || 5173),
  };
}

function parseEnvFile(file) {
  const out = {};
  if (!existsSync(file)) return out;
  for (const line of readFileSync(file, "utf8").split("\n")) {
    const m = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
    if (m) out[m[1]] = m[2];
  }
  return out;
}

// Ports are strict: if something else already holds API_PORT/UI_PORT, say so
// and stop instead of silently picking another (README.md).
async function checkPortsStrict(ports) {
  for (const [name, port] of Object.entries(ports)) {
    if (await portInUse(port)) {
      fail("dev", `port ${port} (${name.toUpperCase()}_PORT) is already in use -- stop whatever's on it or set ${name.toUpperCase()}_PORT`);
      process.exit(1);
    }
  }
}

// 2. docker compose up -d app_db geo_db redis, wait for all three healthy.
async function step2_infra() {
  status("db", "starting app_db, geo_db, redis...");
  const up = spawnSync("docker", ["compose", "up", "-d", "app_db", "geo_db", "redis"], {
    cwd: ROOT,
    stdio: ["ignore", "pipe", "pipe"],
    shell: process.platform === "win32",
    encoding: "utf8",
  });
  if (up.status !== 0) {
    fail("db", "docker compose up failed -- is Docker running?");
    logAndExit("dev", up);
  }

  const ok = await waitUntil(
    "db",
    async () => {
      const ps = spawnSync(
        "docker",
        ["compose", "ps", "--format", "json", "app_db", "geo_db", "redis"],
        { cwd: ROOT, encoding: "utf8", shell: process.platform === "win32" },
      );
      if (ps.status !== 0) return false;
      const lines = ps.stdout.trim().split("\n").filter(Boolean);
      if (lines.length < 3) return false;
      return lines.every((l) => {
        try {
          const svc = JSON.parse(l);
          return svc.Health === "healthy";
        } catch {
          return false;
        }
      });
    },
    { timeoutMs: 120_000 },
  );

  if (!ok) {
    fail("db", "app_db/geo_db/redis did not become healthy within 120s -- check `docker compose logs`");
    process.exit(1);
  }
  status("db", "healthy");
}

// 3. backend/.venv, pip install -e ".[dev]", playwright install chromium.
async function step3_backendInstall() {
  if (!existsSync(path.join(BACKEND, ".venv"))) {
    status("api", "creating backend/.venv...");
    const r = spawnSync(process.platform === "win32" ? "python" : "python3", ["-m", "venv", ".venv"], {
      cwd: BACKEND,
      stdio: "pipe",
      shell: process.platform === "win32",
    encoding: "utf8",
    });
    if (r.status !== 0) {
      fail("api", "venv creation failed");
      logAndExit("dev", r);
    }
  }

  status("api", "pip install -e \".[dev]\" (first run only, can take a while)...");
  const pip = spawnSync(venvPip(), ["install", "-e", ".[dev]"], {
    cwd: BACKEND,
    stdio: "pipe",
    shell: process.platform === "win32",
    encoding: "utf8",
  });
  logToFile("pip-install", pip);
  if (pip.status !== 0) {
    fail("api", `pip install failed -- see ${path.join("logs", "pip-install.log")}`);
    process.exit(1);
  }

  status("api", "playwright install chromium (first run only)...");
  const pw = spawnSync(venvPython(), ["-m", "playwright", "install", "chromium"], {
    cwd: BACKEND,
    stdio: "pipe",
    shell: process.platform === "win32",
    encoding: "utf8",
  });
  logToFile("playwright-install", pw);
  if (pw.status !== 0) {
    fail("api", `playwright install failed -- see ${path.join("logs", "playwright-install.log")}`);
    process.exit(1);
  }
  status("api", "backend deps ready");
}

// 4. npm install in frontend/.
async function step4_frontendInstall() {
  if (existsSync(path.join(FRONTEND, "node_modules"))) {
    status("ui", "frontend deps already installed");
    return;
  }
  status("ui", "npm install (first run only)...");
  const r = spawnSync("npm", ["install"], {
    cwd: FRONTEND,
    stdio: "pipe",
    shell: process.platform === "win32",
    encoding: "utf8",
  });
  logToFile("npm-install", r);
  if (r.status !== 0) {
    fail("ui", `npm install failed -- see ${path.join("logs", "npm-install.log")}`);
    process.exit(1);
  }
  status("ui", "frontend deps ready");
}

// 5. alembic to app@head and geo@head.
async function step5_migrate() {
  status("db", "running migrations (app@head, geo@head)...");
  for (const target of ["app", "geo"]) {
    const r = spawnSync(venvPython(), ["-m", "alembic", "-x", `target=${target}`, "upgrade", `${target}@head`], {
      cwd: BACKEND,
      stdio: "pipe",
      shell: process.platform === "win32",
      encoding: "utf8",
      env: { ...process.env, LOG_FORMAT: "text" },
    });
    logToFile(`migrate-${target}`, r);
    if (r.status !== 0) {
      fail("db", `alembic ${target}@head failed -- see ${path.join("logs", `migrate-${target}.log`)}`);
      process.exit(1);
    }
  }
  status("db", "migrations up to date");
}

// 6. dev user + license.
async function step6_devUser() {
  status("api", "provisioning dev@local.test...");
  const r = spawnSync(venvPython(), ["scripts/create_user.py", "dev@local.test", "devpassword"], {
    cwd: BACKEND,
    stdio: "pipe",
    shell: process.platform === "win32",
    encoding: "utf8",
    env: { ...process.env, LOG_FORMAT: "text" },
  });
  logToFile("create-user", r);
  if (r.status !== 0) {
    fail("api", `dev user provisioning failed -- see ${path.join("logs", "create-user.log")}`);
    process.exit(1);
  }
  status("api", "dev@local.test / devpassword ready");
}

async function runCreateUser(extraArgs) {
  status("api", `provisioning ${extraArgs[0] ?? "user"}...`);
  const r = spawnSync(venvPython(), ["scripts/create_user.py", ...extraArgs], {
    cwd: BACKEND,
    stdio: "inherit",
    shell: process.platform === "win32",
    env: { ...process.env, LOG_FORMAT: "text" },
  });
  process.exit(r.status ?? 1);
}

// 7. uvicorn + celery worker + vite, one Ctrl-C stops all three.
async function step7_start(ports) {
  // Full structured logs go to logs/api.log / logs/worker.log via the app's
  // own RotatingFileHandler (LOG_FILE); the console handler is raised to
  // WARNING so routine INFO lifecycle lines stay out of the terminal. This is
  // on top of runLogged's own stdout/stderr capture below, which still
  // catches anything printed outside the app's logging setup (tracebacks,
  // pip/alembic output during earlier steps, etc).
  const apiEnv = {
    ...process.env,
    LOG_FORMAT: process.env.LOG_FORMAT || "text",
    LOG_FILE: path.join(LOG_DIR, "api.log"),
    CONSOLE_LOG_LEVEL: process.env.CONSOLE_LOG_LEVEL || "WARNING",
  };
  const workerEnv = {
    ...process.env,
    LOG_FORMAT: process.env.LOG_FORMAT || "text",
    LOG_FILE: path.join(LOG_DIR, "worker-app.log"),
    CONSOLE_LOG_LEVEL: process.env.CONSOLE_LOG_LEVEL || "WARNING",
  };
  const env = { ...process.env, LOG_FORMAT: process.env.LOG_FORMAT || "text" };

  const api = trackChild(
    "api",
    runLogged("api", venvPython(), ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(ports.api)], {
      cwd: BACKEND,
      env: apiEnv,
    }),
  );
  onExitReport("api", api.child);

  status("api", `starting on http://127.0.0.1:${ports.api} (logs/api.log)`);
  const apiReady = await waitUntil("api", () => httpOk(`http://127.0.0.1:${ports.api}/api/health`), {
    timeoutMs: 30_000,
  });
  if (!apiReady) {
    fail("api", `did not answer /api/health within 30s -- see ${path.join("logs", "api.log")}`);
    shutdown(1);
    return;
  }
  status("api", "ready");

  if (!noWorker) {
    // Celery's prefork pool doesn't run on Windows; --pool=threads with a
    // fixed ceiling is what lets the Settings-page concurrency slider stay
    // the only live control (see backend/.env.example's note on this).
    // The ceiling itself must stay well below the thread pool's max, though:
    // each thread that actually picks up a scrape task launches its own
    // headless Chromium, and 64 of those at once exhausts a dev machine's
    // RAM/page file (see logs/worker.log's "JavaScript heap out of memory" /
    // "paging file is too small" incidents). Override with
    // CELERY_DEV_CONCURRENCY if a bigger box can take more.
    const devConcurrency = process.env.CELERY_DEV_CONCURRENCY || "8";
    const poolArgs =
      process.platform === "win32"
        ? ["--pool=threads", `--concurrency=${devConcurrency}`]
        : [`--concurrency=${devConcurrency}`];
    const worker = trackChild(
      "worker",
      runLogged(
        "worker",
        venvPython(),
        [
          "-m",
          "celery",
          "-A",
          "app.core.celery_app.celery_app",
          "worker",
          "-Q",
          "google_maps,bing_maps,places,exports",
          "--loglevel=info",
          ...poolArgs,
        ],
        { cwd: BACKEND, env: workerEnv },
      ),
    );
    onExitReport("worker", worker.child);
    status("worker", "starting (logs/worker.log)");
  } else {
    status("worker", "skipped (--no-worker)");
  }

  const ui = trackChild("ui", runLogged("ui", "npm", ["run", "dev", "--", "--port", String(ports.ui)], { cwd: FRONTEND, env }));
  onExitReport("ui", ui.child);

  // "localhost", not "127.0.0.1": Vite's dev server here only answers on the
  // loopback name Node's DNS resolves to ::1, not the literal IPv4 address --
  // probing 127.0.0.1 direct always reads as down even once Vite is ready.
  const uiReady = await waitUntil("ui", () => httpOk(`http://localhost:${ports.ui}`), { timeoutMs: 30_000 });
  if (!uiReady) {
    fail("ui", `did not come up within 30s -- see ${path.join("logs", "ui.log")}`);
    shutdown(1);
    return;
  }
  status("ui", `ready on http://127.0.0.1:${ports.ui}`);

  if (!noOpen) {
    openBrowser(`http://localhost:${ports.ui}`);
  }

  await appendSummary(`dev up: api=${ports.api} ui=${ports.ui} worker=${!noWorker}`);
  status("dev", "");
  status("dev", `UI    http://localhost:${ports.ui}`);
  status("dev", `API   http://localhost:${ports.api}/docs`);
  status("dev", "Login dev@local.test / devpassword");
  status("dev", "Ctrl-C to stop. Full logs are under logs/*.log.");
}

function openBrowser(url) {
  const opener =
    process.platform === "win32" ? "cmd" : process.platform === "darwin" ? "open" : "xdg-open";
  const args = process.platform === "win32" ? ["/c", "start", "", url] : [url];
  spawnSync(opener, args, { stdio: "ignore", shell: false });
}

function onExitReport(label, child) {
  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    if (code !== 0 && code !== null) {
      fail(label, `exited unexpectedly (code ${code}) -- see logs/${label}.log`);
    }
  });
}

function logToFile(name, result) {
  const p = path.join(LOG_DIR, `${name}.log`);
  const chunks = [];
  if (result.stdout) chunks.push(result.stdout);
  if (result.stderr) chunks.push(result.stderr);
  appendFileSync(p, `\n----- ${new Date().toISOString()} -----\n${chunks.join("\n")}\n`);
}

function logAndExit(label, result) {
  logToFile("dev-error", result);
  fail(label, `see ${path.join("logs", "dev-error.log")}`);
  process.exit(1);
}

main().catch((err) => {
  fail("dev", err?.stack || String(err));
  process.exit(1);
});
