/**
 * Role-Based Access Control (RBAC) utilities
 * Provides permission checking and role-based UI rendering
 */

import type { Permission, User, UserRole } from '../types';

// Role to permissions mapping (must match backend)
const ROLE_PERMISSIONS: Record<UserRole, Set<Permission>> = {
    admin: new Set([
        // Full access to everything
        'view_alerts',
        'create_alerts',
        'update_alerts',
        'delete_alerts',
        'ack_alerts',
        'mark_false_positive',
        'view_incidents',
        'create_incidents',
        'update_incidents',
        'delete_incidents',
        'view_models',
        'deploy_models',
        'train_models',
        'view_users',
        'create_users',
        'update_users',
        'delete_users',
        'view_config',
        'update_config',
        'view_audit_logs',
        'manage_integrations',
    ]),
    analyst: new Set([
        // Alert and incident management
        'view_alerts',
        'update_alerts',
        'ack_alerts',
        'mark_false_positive',
        'view_incidents',
        'create_incidents',
        'update_incidents',
        'view_models',
        'view_config',
    ]),
    viewer: new Set([
        // Read-only access
        'view_alerts',
        'view_incidents',
        'view_models',
        'view_config',
    ]),
    auditor: new Set([
        // Audit and compliance access
        'view_alerts',
        'view_incidents',
        'view_models',
        'view_config',
        'view_audit_logs',
    ]),
};

/**
 * Check if a user has a specific permission
 */
export function hasPermission(user: User | null, permission: Permission): boolean {
    if (!user || !user.role) {
        return false;
    }

    const rolePermissions = ROLE_PERMISSIONS[user.role];
    return rolePermissions?.has(permission) || false;
}

/**
 * Check if a user has any of the specified permissions
 */
export function hasAnyPermission(user: User | null, permissions: Permission[]): boolean {
    return permissions.some(permission => hasPermission(user, permission));
}

/**
 * Check if a user has all of the specified permissions
 */
export function hasAllPermissions(user: User | null, permissions: Permission[]): boolean {
    return permissions.every(permission => hasPermission(user, permission));
}

/**
 * Get all permissions for a user's role
 */
export function getUserPermissions(user: User | null): Permission[] {
    if (!user || !user.role) {
        return [];
    }

    const rolePermissions = ROLE_PERMISSIONS[user.role];
    return rolePermissions ? Array.from(rolePermissions) : [];
}

/**
 * Check if user can acknowledge alerts
 */
export function canAcknowledgeAlerts(user: User | null): boolean {
    return hasPermission(user, 'ack_alerts');
}

/**
 * Check if user can mark alerts as false positive
 */
export function canMarkFalsePositive(user: User | null): boolean {
    return hasPermission(user, 'mark_false_positive');
}

/**
 * Check if user can manage incidents
 */
export function canManageIncidents(user: User | null): boolean {
    return hasAnyPermission(user, ['create_incidents', 'update_incidents']);
}

/**
 * Check if user can manage models
 */
export function canManageModels(user: User | null): boolean {
    return hasAnyPermission(user, ['deploy_models', 'train_models']);
}

/**
 * Check if user can manage users
 */
export function canManageUsers(user: User | null): boolean {
    return hasAnyPermission(user, ['create_users', 'update_users', 'delete_users']);
}

/**
 * Check if user is admin
 */
export function isAdmin(user: User | null): boolean {
    return user?.role === 'admin';
}

/**
 * Get user role display name
 */
export function getRoleDisplayName(role: UserRole): string {
    const roleNames: Record<UserRole, string> = {
        admin: 'Administrator',
        analyst: 'Security Analyst',
        viewer: 'Viewer',
        auditor: 'Auditor',
    };
    return roleNames[role] || role;
}

/**
 * Get role badge color
 */
export function getRoleBadgeColor(role: UserRole): string {
    const colors: Record<UserRole, string> = {
        admin: '#dc3545',      // red
        analyst: '#007bff',    // blue
        viewer: '#6c757d',     // gray
        auditor: '#ffc107',    // yellow
    };
    return colors[role] || '#6c757d';
}
