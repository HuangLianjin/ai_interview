/**
 * API 配置公共模块
 * 统一管理 API 基础 URL 和请求工具
 */

import { getToken, clearAuth } from '../auth';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

/**
 * 获取用户 ID（从 localStorage）
 * 与 useUserIdentity.ts 使用相同的 key: interview_ai_user_id
 */
export function getUserId(): string {
    if (typeof window === 'undefined') return 'default_user';
    return localStorage.getItem('interview_ai_user_id') || 'default_user';
}

/**
 * 通用认证请求头：自动附带 JWT 令牌和用户ID
 */
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
    const token = getToken();
    const userId = getUserId();
    return {
        'X-User-ID': userId,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...extra,
    };
}

function handleUnauthorized(response: Response) {
    if (response.status === 401) {
        clearAuth();
        if (typeof window !== 'undefined') window.location.href = '/?need_login=1';
    }
}

/**
 * 统一的 API 请求处理
 */
export async function apiRequest<T>(
    url: string,
    options?: RequestInit
): Promise<T> {
    const userId = getUserId();

    const response = await fetch(`${API_BASE_URL}${url}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'X-User-ID': userId,
            'Authorization': `Bearer ${getToken() || ''}`,
            ...options?.headers,
        },
    });
    handleUnauthorized(response);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
        throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
}

/**
 * 带认证的 fetch（不解析响应，用于流式请求等）
 */
export async function authFetch(
    url: string,
    options?: RequestInit
): Promise<Response> {
    const userId = getUserId();

    const response = await fetch(`${API_BASE_URL}${url}`, {
        ...options,
        headers: {
            'X-User-ID': userId,
            'Authorization': `Bearer ${getToken() || ''}`,
            ...options?.headers,
        },
    });
    handleUnauthorized(response);
    return response;
}