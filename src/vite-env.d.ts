/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_SPLINE_SCENE?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
