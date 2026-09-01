/** 认证 API：验证码、注册、登录、个人资料。 */
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

export async function sendCode(phone: string): Promise<{ success: boolean; message: string; debug_code?: string; expires_in?: number }> {
    const res = await fetch(`${BASE}/api/auth/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || '验证码发送失败');
    return data;
}

export async function register(phone: string, code: string, password: string): Promise<{ success: boolean; token: string; phone: string; nickname?: string; avatar?: string }> {
    const res = await fetch(`${BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, code, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || '注册失败');
    return data;
}

export async function login(phone: string, password: string): Promise<{ success: boolean; token: string; phone: string; nickname?: string; avatar?: string }> {
    const res = await fetch(`${BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || '登录失败');
    return data;
}

export async function getMe(): Promise<{ success: boolean; phone: string; nickname: string; avatar: string }> {
    return authFetch('/api/auth/me');
}

export async function updateProfile(nickname: string, avatar: string): Promise<{ success: boolean; nickname: string; avatar: string }> {
    return authFetch('/api/auth/profile', {
        method: 'PUT',
        body: JSON.stringify({ nickname, avatar }),
    });
}

export async function uploadAvatar(file: File): Promise<{ success: boolean; avatar: string }> {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${BASE}/api/auth/avatar`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken() || ''}` },
        body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || '头像上传失败');
    return data;
}