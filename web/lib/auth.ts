/** 登录态管理：本地存储令牌、昵称、头像，30 分钟过期。 */
const TOKEN_KEY = 'ai_interview_token';
const PHONE_KEY = 'ai_interview_phone';
const NICKNAME_KEY = 'ai_interview_nickname';
const AVATAR_KEY = 'ai_interview_avatar';
const EXPIRES_KEY = 'ai_interview_token_expires';

const TTL_MS = 30 * 60 * 1000;

export function saveAuth(token: string, phone: string, nickname = '', avatar = 'teal') {
    if (typeof window === 'undefined') return;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(PHONE_KEY, phone);
    localStorage.setItem(NICKNAME_KEY, nickname);
    localStorage.setItem(AVATAR_KEY, avatar);
    localStorage.setItem(EXPIRES_KEY, String(Date.now() + TTL_MS));
}

export function saveProfile(nickname: string, avatar: string) {
    if (typeof window === 'undefined') return;
    localStorage.setItem(NICKNAME_KEY, nickname);
    localStorage.setItem(AVATAR_KEY, avatar);
}

export function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    const token = localStorage.getItem(TOKEN_KEY);
    const expires = Number(localStorage.getItem(EXPIRES_KEY) || 0);
    if (!token || !expires || Date.now() >= expires) {
        clearAuth();
        return null;
    }
    return token;
}

export function getPhone(): string {
    if (typeof window === 'undefined') return '';
    return localStorage.getItem(PHONE_KEY) || '';
}

export function getNickname(): string {
    if (typeof window === 'undefined') return '';
    return localStorage.getItem(NICKNAME_KEY) || '';
}

export function getAvatar(): string {
    if (typeof window === 'undefined') return 'teal';
    return localStorage.getItem(AVATAR_KEY) || 'teal';
}

export function isAuthenticated(): boolean {
    return !!getToken();
}

export function clearAuth() {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PHONE_KEY);
    localStorage.removeItem(NICKNAME_KEY);
    localStorage.removeItem(AVATAR_KEY);
    localStorage.removeItem(EXPIRES_KEY);
}