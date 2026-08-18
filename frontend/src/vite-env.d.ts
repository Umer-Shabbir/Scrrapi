/// <reference types="vite/client" />

// Vite injects VITE_* at build time. Declaring them here is what makes
// `import.meta.env.VITE_API_BASE_URL` typed rather than a TS2339 under
// `tsc --noEmit` (the CI typecheck runs without Vite's own transform).
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_WS_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
