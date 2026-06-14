// 移动端API基址配置。H5生产包可使用auto跟随当前域名；原生App/小程序需显式配置后端域名或局域网IP。
const configuredApiBase = import.meta.env.VITE_API_BASE;
const configuredWsBase = import.meta.env.VITE_WS_BASE;

function autoApiBase() {
  if (typeof window !== 'undefined' && window.location?.host) {
    return `${window.location.protocol}//${window.location.host}/api/v1`;
  }
  return 'http://10.211.16.93:8000/api/v1';
}

function autoWsBase() {
  if (typeof window !== 'undefined' && window.location?.host) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/realtime`;
  }
  return 'ws://10.211.16.93:8000/ws/realtime';
}

export const API_BASE = configuredApiBase && configuredApiBase !== 'auto' ? configuredApiBase : autoApiBase();
export const WS_BASE = configuredWsBase && configuredWsBase !== 'auto' ? configuredWsBase : autoWsBase();
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
