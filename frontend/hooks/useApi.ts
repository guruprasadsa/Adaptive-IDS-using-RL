/**
 * frontend/hooks/useApi.ts
 * Custom React hooks for API data fetching with caching and real-time updates
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiService } from '../api';
import type { 
    Alert, 
    Incident, 
    DashboardStats, 
    AlertsResponse, 
    IncidentsResponse,
    ModelMetrics,
    PredictionResult,
    User
} from '../types';

// Query keys for consistent cache management
export const queryKeys = {
    health: ['health'] as const,
    dashboardStats: ['dashboard', 'stats'] as const,
    alerts: (page: number, perPage: number, filters: Record<string, any>) => 
        ['alerts', { page, perPage, ...filters }] as const,
    alert: (id: string) => ['alert', id] as const,
    incidents: (page: number, perPage: number, filters: Record<string, any>) =>
        ['incidents', { page, perPage, ...filters }] as const,
    incident: (id: string) => ['incident', id] as const,
    modelMetrics: ['model', 'metrics'] as const,
    currentUser: ['user', 'me'] as const,
};

// Health check hook
export function useHealthCheck(options?: Partial<UseQueryOptions<any, Error>>) {
    return useQuery({
        queryKey: queryKeys.health,
        queryFn: () => apiService.healthCheck(),
        refetchInterval: 30000, // Check every 30 seconds
        retry: 1,
        ...options,
    });
}

// Dashboard stats hook
export function useDashboardStats(options?: Partial<UseQueryOptions<DashboardStats, Error>>) {
    return useQuery({
        queryKey: queryKeys.dashboardStats,
        queryFn: () => apiService.getDashboardStats(),
        staleTime: 30000, // Consider data stale after 30 seconds
        refetchInterval: 60000, // Refetch every minute
        ...options,
    });
}

// Alerts hooks
export function useAlerts(
    page: number = 1,
    perPage: number = 10,
    filters: Record<string, any> = {},
    options?: Partial<UseQueryOptions<AlertsResponse, Error>>
) {
    return useQuery({
        queryKey: queryKeys.alerts(page, perPage, filters),
        queryFn: () => apiService.getAlerts(page, perPage, filters),
        staleTime: 10000, // 10 seconds
        keepPreviousData: true, // Keep previous data while fetching new page
        ...options,
    });
}

export function useAlert(id: string, options?: Partial<UseQueryOptions<Alert, Error>>) {
    return useQuery({
        queryKey: queryKeys.alert(id),
        queryFn: () => apiService.getAlert(id),
        enabled: !!id,
        staleTime: 30000,
        ...options,
    });
}

// Incidents hooks
export function useIncidents(
    page: number = 1,
    perPage: number = 10,
    filters: Record<string, any> = {},
    options?: Partial<UseQueryOptions<IncidentsResponse, Error>>
) {
    return useQuery({
        queryKey: queryKeys.incidents(page, perPage, filters),
        queryFn: () => apiService.getIncidents(page, perPage, filters),
        staleTime: 10000,
        keepPreviousData: true,
        ...options,
    });
}

export function useIncident(id: string, options?: Partial<UseQueryOptions<Incident, Error>>) {
    return useQuery({
        queryKey: queryKeys.incident(id),
        queryFn: () => apiService.getIncident(id),
        enabled: !!id,
        staleTime: 30000,
        ...options,
    });
}

// Model metrics hook
export function useModelMetrics(options?: Partial<UseQueryOptions<ModelMetrics, Error>>) {
    return useQuery({
        queryKey: queryKeys.modelMetrics,
        queryFn: () => apiService.getModelMetrics(),
        staleTime: 300000, // 5 minutes - metrics don't change often
        ...options,
    });
}

// Current user hook
export function useCurrentUser(options?: Partial<UseQueryOptions<User, Error>>) {
    return useQuery({
        queryKey: queryKeys.currentUser,
        queryFn: () => apiService.getCurrentUser(),
        staleTime: Infinity, // User data rarely changes
        retry: false,
        ...options,
    });
}

// Mutation hooks for data updates
export function useUpdateAlertStatus(options?: UseMutationOptions<Alert, Error, { id: string; status: string }>) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, status }) => apiService.updateAlertStatus(id, status),
        onSuccess: (data, variables) => {
            // Invalidate and refetch relevant queries
            queryClient.invalidateQueries({ queryKey: queryKeys.alert(variables.id) });
            queryClient.invalidateQueries({ queryKey: ['alerts'] });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
        },
        ...options,
    });
}

export function useUpdateIncidentStatus(
    options?: UseMutationOptions<Incident, Error, { id: string; status: string }>
) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, status }) => apiService.updateIncidentStatus(id, status),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.incident(variables.id) });
            queryClient.invalidateQueries({ queryKey: ['incidents'] });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
        },
        ...options,
    });
}

// Prediction mutation
export function usePredict(
    options?: UseMutationOptions<PredictionResult, Error, Record<string, any>>
) {
    return useMutation({
        mutationFn: (data) => apiService.predict(data),
        ...options,
    });
}

// Model retrain mutation
export function useRetrainModel(
    options?: UseMutationOptions<{ status: string; message: string }, Error, void>
) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => apiService.retrainModel(),
        onSuccess: () => {
            // After retraining, invalidate model metrics
            queryClient.invalidateQueries({ queryKey: queryKeys.modelMetrics });
        },
        ...options,
    });
}

// Authentication mutations
export function useLogin(
    options?: UseMutationOptions<any, Error, { emailOrUsername: string; password: string }>
) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ emailOrUsername, password }) => apiService.login(emailOrUsername, password),
        onSuccess: () => {
            // Fetch user data after login
            queryClient.invalidateQueries({ queryKey: queryKeys.currentUser });
        },
        ...options,
    });
}

export function useLogout(options?: UseMutationOptions<void, Error, void>) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => apiService.logout(),
        onSuccess: () => {
            // Clear all cached data on logout
            queryClient.clear();
        },
        ...options,
    });
}

export function useRegister(
    options?: UseMutationOptions<any, Error, { username: string; email: string; password: string }>
) {
    return useMutation({
        mutationFn: ({ username, email, password }) => apiService.register(username, email, password),
        ...options,
    });
}

// Utility hook for invalidating specific queries
export function useInvalidateQueries() {
    const queryClient = useQueryClient();

    return {
        invalidateAlerts: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
        invalidateIncidents: () => queryClient.invalidateQueries({ queryKey: ['incidents'] }),
        invalidateDashboard: () => queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats }),
        invalidateAll: () => queryClient.invalidateQueries(),
    };
}

// Prefetch utility for better UX
export function usePrefetch() {
    const queryClient = useQueryClient();

    return {
        prefetchAlert: (id: string) => {
            queryClient.prefetchQuery({
                queryKey: queryKeys.alert(id),
                queryFn: () => apiService.getAlert(id),
            });
        },
        prefetchIncident: (id: string) => {
            queryClient.prefetchQuery({
                queryKey: queryKeys.incident(id),
                queryFn: () => apiService.getIncident(id),
            });
        },
    };
}
