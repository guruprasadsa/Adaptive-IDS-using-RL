/**
 * frontend/services/authService.ts
 * Authentication service for managing user authentication state
 */

import { apiService } from '../apiService';
import type { LoginResponse, User } from '../types';

export type AuthState = {
    isAuthenticated: boolean;
    user: User | null;
    isLoading: boolean;
};

export class AuthService {
    private authState: AuthState = {
        isAuthenticated: false,
        user: null,
        isLoading: false
    };
    private authListeners: Array<(state: AuthState) => void> = [];

    constructor() {
        // Check if user is already authenticated on init
        this.checkAuthStatus();
        
        // Listen for logout events from API client
        window.addEventListener('auth:logout', () => {
            this.handleLogout();
        });
    }

    /**
     * Subscribe to authentication state changes
     */
    subscribe(listener: (state: AuthState) => void): () => void {
        this.authListeners.push(listener);
        // Immediately call with current state
        listener(this.authState);
        
        // Return unsubscribe function
        return () => {
            this.authListeners = this.authListeners.filter(l => l !== listener);
        };
    }

    /**
     * Notify all listeners of state change
     */
    private notifyListeners(): void {
        this.authListeners.forEach(listener => listener(this.authState));
    }

    /**
     * Update auth state
     */
    private updateState(updates: Partial<AuthState>): void {
        this.authState = { ...this.authState, ...updates };
        this.notifyListeners();
    }

    /**
     * Get current auth state
     */
    getState(): AuthState {
        return { ...this.authState };
    }

    /**
     * Check if user is authenticated by validating token
     */
    private async checkAuthStatus(): Promise<void> {
        const isAuthenticated = apiService.isAuthenticated();
        
        if (!isAuthenticated) {
            this.updateState({ isAuthenticated: false, user: null });
            return;
        }

        // Validate token by fetching user info
        try {
            this.updateState({ isLoading: true });
            const user = await apiService.getCurrentUser();
            this.updateState({
                isAuthenticated: true,
                user,
                isLoading: false
            });
        } catch (error: any) {
            // Only log if it's not a simple "no token" scenario
            if (error.status !== 401) {
                console.error('Failed to validate authentication:', error);
            }
            // Token is invalid, clear it
            apiService.clearTokens();
            this.updateState({
                isAuthenticated: false,
                user: null,
                isLoading: false
            });
        }
    }

    /**
     * Login with email/username and password
     */
    async login(emailOrUsername: string, password: string): Promise<{ success: boolean; error?: string }> {
        try {
            this.updateState({ isLoading: true });
            
            const response: LoginResponse = await apiService.login(emailOrUsername, password);
            
            this.updateState({
                isAuthenticated: true,
                user: response.user,
                isLoading: false
            });

            console.log('Login successful:', response.user.username);
            
            return { success: true };
        } catch (error: any) {
            console.error('Login failed:', error);
            
            this.updateState({ isLoading: false });
            
            const errorMessage = error.message || 'Login failed. Please try again.';
            return { success: false, error: errorMessage };
        }
    }

    /**
     * Logout user
     */
    async logout(): Promise<void> {
        try {
            await apiService.logout();
        } catch (error) {
            console.error('Logout API call failed:', error);
        } finally {
            this.handleLogout();
        }
    }

    /**
     * Handle logout (clear state and tokens)
     */
    private handleLogout(): void {
        this.updateState({
            isAuthenticated: false,
            user: null,
            isLoading: false
        });
        
        console.log('User logged out');
    }

    /**
     * Refresh user data
     */
    async refreshUser(): Promise<void> {
        if (!this.authState.isAuthenticated) {
            return;
        }

        try {
            const user = await apiService.getCurrentUser();
            this.updateState({ user });
        } catch (error) {
            console.error('Failed to refresh user data:', error);
            // If refresh fails, user might be logged out
            await this.checkAuthStatus();
        }
    }

    /**
     * Check if user has a specific role
     */
    hasRole(role: string): boolean {
        return this.authState.user?.role === role;
    }

    /**
     * Get current user
     */
    getCurrentUser(): User | null {
        return this.authState.user;
    }
}

// Export singleton instance
export const authService = new AuthService();
