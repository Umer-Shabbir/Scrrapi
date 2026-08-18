// Frontend/design gap: `npm run lint` (package.json:10) had no config to run
// against -- `.eslintrc*` was missing entirely, so the script errored
// immediately instead of linting anything. This is the legacy-format config
// ESLint 8.x (the installed major, see package.json) expects; flat config
// (eslint.config.js) is a v9+ convention this project isn't on yet.
module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react", "react-hooks", "react-refresh"],
  settings: {
    react: { version: "detect" },
  },
  ignorePatterns: ["dist", "node_modules", "*.cjs"],
  rules: {
    // React 17+ JSX transform -- no `import React` needed per file, and this
    // codebase's components don't add one (see any page under src/pages).
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    // Convention across this codebase (see api/client.ts's ApiError, every
    // page's `catch` blocks): unused vars prefixed `_` are intentional
    // placeholders, not dead code.
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "off",
  },
};
