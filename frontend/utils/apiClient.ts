/**
 * frontend/utils/apiClient.ts
 * Enhanced API client with request/response interceptors, retry logic, and caching
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

// API Configuration
// Use empty string for production (nginx proxy), localhost:5001 for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined && import.meta.env.VITE_API_BASE_URL !== '' 
    ? import.meta.env.VITE_API_BASE_URL 
    : (import.meta.env.DEV ? 'http://localhost:5001' : '');
const API_VERSION = import.meta.env.VITE_API_VERSION || 'v1';
const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || '30000', 10);
const ENABLE_LOGGING = import.meta.env.VITE_ENABLE_API_LOGGING === 'true';

// Token storage keys
const ACCESS_TOKEN_KEY = 'adaptive_ids_access_token';
const REFRESH_TOKEN_KEY = 'adaptive_ids_refresh_token';

// Simple in-memory cache
interface CacheEntry {
    data: any;
    timestamp: number;
    ttl: number;
}

class ApiCache {
    private cache: Map<string, CacheEntry> = new Map();

    set(key: string, data: any, ttl: number = 300000): void {
        this.cache.set(key, {
            data,
            timestamp: Date.now(),
            ttl
        });
    }

    get(key: string): any | null {
        const entry = this.cache.get(key);
        if (!entry) return null;

        const now = Date.now();
        if (now - entry.timestamp > entry.ttl) {
            this.cache.delete(key);
            return null;
        }

        return entry.data;
    }

    clear(): void {
        this.cache.clear();
    }

    remove(key: string): void {
        this.cache.delete(key);
    }
}

const apiCache = new ApiCache();

// Token management
export const tokenManager = {
    getAccessToken(): string | null {
        return localStorage.getItem(ACCESS_TOKEN_KEY);
    },

    getRefreshToken(): string | null {
        return localStorage.getItem(REFRESH_TOKEN_KEY);
    },

    setTokens(accessToken: string, refreshToken: string): void {
        localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    },

    clearTokens(): void {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
    },

    isAuthenticated(): boolean {
        return !!this.getAccessToken();
    }
};

// Custom error class for API errors
export class ApiError extends Error {
    constructor(
        message: string,
        public status?: number,
        public code?: string,
        public response?: any
    ) {
        super(message);
        this.name = 'ApiError';
    }
}

// Create axios instance
const apiClient: AxiosInstance = axios.create({
    baseURL: `${API_BASE_URL}/api`,
    timeout: API_TIMEOUT,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // Add access token to headers
        const accessToken = tokenManager.getAccessToken();
        if (accessToken && config.headers) {
            config.headers.Authorization = `Bearer ${accessToken}`;
        }

        // Log request in development
        if (ENABLE_LOGGING) {
            console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.data);
        }

        // Add request timestamp for performance tracking
        (config as any).metadata = { startTime: Date.now() };

        return config;
    },
    (error) => {
        console.error('[API Request Error]', error);
        return Promise.reject(error);
    }
);

// Response interceptor
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(callback: (token: string) => void) {
    refreshSubscribers.push(callback);
}

function onTokenRefreshed(token: string) {
    refreshSubscribers.forEach((callback) => callback(token));
    refreshSubscribers = [];
}

apiClient.interceptors.response.use(
    (response: AxiosResponse) => {
        // Log response in development
        if (ENABLE_LOGGING) {
            const duration = Date.now() - (response.config as any).metadata?.startTime;
            console.log(
                `[API Response] ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status} (${duration}ms)`,
                response.data
            );
        }

        return response;
    },
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // Log error in development
        if (ENABLE_LOGGING) {
            console.error('[API Response Error]', {
                url: error.config?.url,
                status: error.response?.status,
                message: error.message,
                data: error.response?.data
            });
        }

        // Handle 401 Unauthorized - try to refresh token
        // BUT: Don't try to refresh on login/register endpoints (they should fail with proper error)
        const isAuthEndpoint = originalRequest?.url?.includes('/auth/login') || 
                              originalRequest?.url?.includes('/auth/register');
        
        if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !isAuthEndpoint) {
            if (isRefreshing) {
                // Wait for token refresh to complete
                return new Promise((resolve) => {
                    subscribeTokenRefresh((token: string) => {
                        if (originalRequest.headers) {
                            originalRequest.headers.Authorization = `Bearer ${token}`;
                        }
                        resolve(apiClient(originalRequest));
                    });
                });
            }

            originalRequest._retry = true;
            isRefreshing = true;

            try {
                const refreshToken = tokenManager.getRefreshToken();
                if (!refreshToken) {
                    throw new Error('No refresh token available');
                }

                const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
                    refresh_token: refreshToken
                });

                const { access_token } = response.data;
                localStorage.setItem(ACCESS_TOKEN_KEY, access_token);

                isRefreshing = false;
                onTokenRefreshed(access_token);

                if (originalRequest.headers) {
                    originalRequest.headers.Authorization = `Bearer ${access_token}`;
                }
                return apiClient(originalRequest);
            } catch (refreshError) {
                isRefreshing = false;
                tokenManager.clearTokens();
                
                // Redirect to login or emit event
                window.dispatchEvent(new CustomEvent('auth:logout'));
                
                return Promise.reject(new ApiError(
                    'Session expired. Please login again.',
                    401,
                    'token_expired'
                ));
            }
        }

        // Transform error to ApiError
        const responseData = error.response?.data as any;
        const apiError = new ApiError(
            responseData?.message || (error instanceof Error ? error.message : 'An error occurred'),
            error.response?.status,
            responseData?.error || 'unknown_error',
            error.response?.data
        );

        return Promise.reject(apiError);
    }
);

// Retry logic for failed requests
export const retryRequest = async <T>(
    requestFn: () => Promise<T>,
    maxRetries: number = 3,
    delay: number = 1000
): Promise<T> => {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            return await requestFn();
        } catch (error) {
            if (attempt === maxRetries) {
                throw error;
            }

            // Don't retry on client errors (4xx) except 429 (too many requests)
            if (error instanceof ApiError && error.status) {
                if (error.status >= 400 && error.status < 500 && error.status !== 429) {
                    throw error;
                }
            }

            // Exponential backoff
            const waitTime = delay * Math.pow(2, attempt);
            console.log(`Retrying request (attempt ${attempt + 1}/${maxRetries}) in ${waitTime}ms...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }
    }

    throw new Error('Max retries exceeded');
};

// Cached GET request
export const cachedGet = async <T>(
    url: string,
    ttl: number = 300000,
    config?: AxiosRequestConfig
): Promise<T> => {
    const cacheKey = `${url}${config ? JSON.stringify(config.params) : ''}`;
    
    // Check cache first
    const cachedData = apiCache.get(cacheKey);
    if (cachedData !== null) {
        if (ENABLE_LOGGING) {
            console.log(`[Cache Hit] ${url}`);
        }
        return cachedData;
    }

    // Fetch from API
    const response = await apiClient.get<T>(url, config);
    
    // Store in cache
    apiCache.set(cacheKey, response.data, ttl);
    
    return response.data;
};

// Clear cache
export const clearCache = (pattern?: string): void => {
    if (pattern) {
        // Clear specific pattern (not implemented in simple cache)
        console.log(`Clearing cache for pattern: ${pattern}`);
    } else {
        apiCache.clear();
    }
};

// Health check with timeout
export const checkHealth = async (timeout: number = 5000): Promise<boolean> => {
    try {
        const response = await axios.get(`${API_BASE_URL}/api/health`, { timeout });
        return response.data.status === 'ok';
    } catch (error) {
        return false;
    }
};

// Debounce helper for search operations
export const debounce = <T extends (...args: any[]) => any>(
    func: T,
    wait: number
): ((...args: Parameters<T>) => void) => {
    let timeout: NodeJS.Timeout | null = null;

    return (...args: Parameters<T>) => {
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
};

export default apiClient;
