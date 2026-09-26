import { invoke } from '@tauri-apps/api/core';
import type { DesktopHost } from './runtime';

export const tauriHost: DesktopHost = {
  configure: (restart) => invoke(restart ? 'restart_desktop_backend' : 'desktop_runtime_config')
};
