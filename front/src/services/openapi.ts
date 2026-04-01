import { OpenAPI } from './generated'

declare global {
  interface Window {
    __ENV?: {
      BACKEND_URL?: string
    }
  }
}

/**
 * 初始化由 OpenAPI 生成的请求客户端。
 *
 * 说明：
 * - 生成接口的路径已包含 `/api/v1/...`，因此 BASE 默认应为空串（同源）或完整后端地址。
 * - 如需直连本地后端，可在应用启动时调用 `initOpenAPI('http://127.0.0.1:8000')`。
 */
export function initOpenAPI(base: string = '') {
  OpenAPI.BASE = base
}

const runtimeBackendUrl = window.__ENV?.BACKEND_URL
const buildtimeBackendUrl = import.meta.env.VITE_BACKEND_URL
initOpenAPI(runtimeBackendUrl ?? buildtimeBackendUrl ?? '')

