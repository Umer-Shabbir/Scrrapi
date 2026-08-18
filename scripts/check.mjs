#!/usr/bin/env node
// Same four gates as CI (.github/workflows/ci.yml): ruff, pytest, tsc
// --noEmit, and a frontend production build. Each gate's full output goes to
// logs/check-<gate>.log; the console only gets a pass/fail line per gate, and
// the full log is dumped to the console only for a gate that actually failed.
import { spawnSync } from "node:child_process";
import { appendFileSync } from "node:fs";
import path from "node:path";
import { BACKEND, FRONTEND, LOG_DIR, status, fail, venvPython } from "./lib.mjs";

const gates = [
  {
    name: "ruff",
    cwd: BACKEND,
    cmd: venvPython(),
    args: ["-m", "ruff", "check", "."],
  },
  {
    name: "pytest",
    cwd: BACKEND,
    cmd: venvPython(),
    args: ["-m", "pytest", "-q"],
    env: {
      APP_DB_URL: process.env.APP_DB_URL || "postgresql+psycopg://leadgen:leadgen@localhost:5434/leadgen_app",
      GEO_DB_URL: process.env.GEO_DB_URL || "postgresql+psycopg://leadgen:leadgen@localhost:5433/leadgen_geo",
      REDIS_URL: process.env.REDIS_URL || "redis://localhost:6379/0",
      JWT_SECRET: process.env.JWT_SECRET || "ci-secret",
      LOG_FORMAT: "text",
    },
  },
  {
    name: "tsc",
    cwd: FRONTEND,
    cmd: "npx",
    args: ["tsc", "--noEmit"],
  },
  {
    name: "build",
    cwd: FRONTEND,
    cmd: "npm",
    args: ["run", "build"],
  },
];

let failed = false;

for (const gate of gates) {
  const r = spawnSync(gate.cmd, gate.args, {
    cwd: gate.cwd,
    shell: process.platform === "win32",
    encoding: "utf8",
    env: { ...process.env, ...gate.env },
  });
  const logPath = path.join(LOG_DIR, `check-${gate.name}.log`);
  appendFileSync(
    logPath,
    `\n----- ${new Date().toISOString()} :: ${gate.cmd} ${gate.args.join(" ")} -----\n${r.stdout ?? ""}\n${r.stderr ?? ""}\n`,
  );

  if (r.status === 0) {
    status("check", `${gate.name} passed`);
  } else {
    failed = true;
    fail("check", `${gate.name} FAILED (see ${path.join("logs", `check-${gate.name}.log`)})`);
    // Surface the failing gate's output directly too -- a failure is exactly
    // the case where "quiet by default" shouldn't hide anything.
    process.stdout.write(`${r.stdout ?? ""}\n${r.stderr ?? ""}\n`);
  }
}

process.exit(failed ? 1 : 0);
