const configuredApiBase = import.meta.env.VITE_API_BASE;
const configuredWsBase = import.meta.env.VITE_WS_BASE;
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

export const API_BASE = configuredApiBase && configuredApiBase !== 'auto' ? configuredApiBase : '/api/v1';
export const WS_BASE =
  configuredWsBase && configuredWsBase !== 'auto'
    ? configuredWsBase
    : `${wsProtocol}//${window.location.host}/ws/realtime`;
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
