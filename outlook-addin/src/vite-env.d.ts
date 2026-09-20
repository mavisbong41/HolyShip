/// <reference types="vite/client" />
/// <reference types="@types/office-js" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_DASHBOARD_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
