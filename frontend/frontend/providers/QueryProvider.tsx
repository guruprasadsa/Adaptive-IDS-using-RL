/**
 * frontend/providers/QueryProvider.tsx
 * React Query provider setup for the application
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Global defaults for queries
      staleTime: 10000, // 10 seconds
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      retry: 1,
      // Show cached data while fetching in background
      refetchOnMount: 'always',
    },
    mutations: {
      // Global defaults for mutations
      retry: 0,
    },
  },
});

interface QueryProviderProps {
  children: React.ReactNode;
}

/**
 * Wrap your app with this provider to enable React Query
 * 
 * Usage:
 * ```tsx
 * import { QueryProvider } from './providers/QueryProvider';
 * 
 * function App() {
 *   return (
 *     <QueryProvider>
 *       <YourApp />
 *     </QueryProvider>
 *   );
 * }
 * ```
 */
export function QueryProvider({ children }: QueryProviderProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* DevTools only in development */}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

export { queryClient };
