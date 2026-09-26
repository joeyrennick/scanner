import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { browserRuntime, type PlatformRuntime } from './runtime';

const PlatformContext = createContext<PlatformRuntime>(browserRuntime);

export function PlatformProvider({ runtime, children }: { runtime: PlatformRuntime; children: ReactNode }) {
  return <PlatformContext.Provider value={runtime}>{children}</PlatformContext.Provider>;
}

export const usePlatform = () => useContext(PlatformContext);
export const useApplicationApi = () => usePlatform().api;
