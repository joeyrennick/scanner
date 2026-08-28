export type AppRoute = {
  path: string;
  title: string;
  navLabel: string;
  description: string;
};

export const appRoutes: AppRoute[] = [
  {
    path: '/',
    title: 'Dashboard',
    navLabel: 'Dashboard',
    description: 'Scanner readiness and cache status'
  },
  {
    path: '/daily-scanner',
    title: 'Daily Scanner',
    navLabel: 'Daily Scanner',
    description: 'Run daily strategy screens and review candidates'
  },
  {
    path: '/candidates',
    title: 'Candidates',
    navLabel: 'Candidates',
    description: 'Review scanner candidates and trade checklist values'
  },
  {
    path: '/fundamentals',
    title: 'Fundamental Analysis',
    navLabel: 'Fundamentals',
    description: 'Evaluate business quality, valuation, and long-term risk'
  },
  {
    path: '/backtest',
    title: 'Backtest',
    navLabel: 'Backtest',
    description: 'Analyze historical strategy performance'
  },
  {
    path: '/portfolio',
    title: 'Portfolio',
    navLabel: 'Portfolio',
    description: 'Review simulated sizing, exposure, and risk'
  },
  {
    path: '/journal',
    title: 'Journal',
    navLabel: 'Journal',
    description: 'Track planned trades and imported broker history'
  },
  {
    path: '/reports',
    title: 'Reports',
    navLabel: 'Reports',
    description: 'Open generated reports and exports'
  },
  {
    path: '/cache-warmup',
    title: 'Cache Warmup',
    navLabel: 'Cache Warmup',
    description: 'Prepare local market data while controlling provider calls'
  },
  {
    path: '/settings',
    title: 'Settings',
    navLabel: 'Settings',
    description: 'Configure market data, risk defaults, and appearance'
  }
];

export function getRouteMeta(pathname: string): AppRoute {
  return appRoutes.find((route) => route.path === pathname) ?? appRoutes[0];
}
