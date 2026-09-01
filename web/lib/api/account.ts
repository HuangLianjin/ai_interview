/** 账号数据闭环：导出、注销、用量统计。 */
import { getToken } from '../auth';

const BASE = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

async function authFetch(path: string, init?: RequestInit) {
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${getToken() || ''}`,
            ...(init?.headers || {}),
        },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || '请求失败');
    return data;
}

export async function getUsageSummary(): Promise<{
    success: boolean;
    summary: {
        request_count: number;
        total_duration_ms: number;
        avg_duration_ms: number;
        error_count: number;
        session_count: number;
        message_count: number;
        resume_count: number;
        generated_resume_count: number;
        profile_count: number;
    };
}> {
    return authFetch('/api/account/usage/summary');
}

export async function exportUserData(): Promise<any> {
    return authFetch('/api/account/export');
}

export async function deleteAccount(): Promise<{ success: boolean; message: string; deleted_user: boolean }> {
    return authFetch('/api/account/delete', { method: 'DELETE' });
}