#!/usr/bin/env node
// Thin wrapper: run a backend/scripts/*.py file with the backend venv's
// python, from the backend/ directory (so `import app.*` resolves), forwarding
// whatever args follow. Used by `npm run seed` and `npm run smoke`.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { BACKEND, status, fail, venvPython } from "./lib.mjs";

const [scriptArg, ...rest] = process.argv.slice(2);
if (!scriptArg) {
  fail("py", "usage: node scripts/py.mjs <backend-relative script path> [args...]");
  process.exit(1);
}

// Accept either "scripts/seed_geo.py" (backend-relative, as package.json
// calls it) or an absolute path.
const scriptPath = path.isAbsolute(scriptArg) ? scriptArg : path.join(BACKEND, scriptArg);
if (!existsSync(scriptPath)) {
  fail("py", `not found: ${scriptPath}`);
  process.exit(1);
}
if (!existsSync(venvPython())) {
  fail("py", "backend/.venv not found -- run `npm run setup` first");
  process.exit(1);
}

status("py", `running ${path.relative(BACKEND, scriptPath)}...`);
const child = spawn(venvPython(), [scriptPath, ...rest], {
  cwd: BACKEND,
  stdio: "inherit",
  env: { ...process.env, LOG_FORMAT: process.env.LOG_FORMAT || "text" },
});
child.on("exit", (code) => process.exit(code ?? 1));
