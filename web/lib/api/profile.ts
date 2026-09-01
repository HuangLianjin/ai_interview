/**
 * 能力画像 API 接口
 */

import { API_BASE_URL, getUserId, authHeaders } from './config';

// 维度评分接口
export interface DimensionScore {
    score: number;
    evidence: string;
    trend?: string;
}

// 能力画像接口
export interface AbilityProfile {
    professional_competence: DimensionScore;
    execution_results: DimensionScore;
    logic_problem_solving: DimensionScore;
    communication: DimensionScore;
    growth_potential: DimensionScore;
    collaboration: DimensionScore;
    skill_tags: string[];
    overall_assessment?: string;
    key_strengths?: string[];
    key_weaknesses?: string[];
    recommendation?: string;
    confidence?: number;
    last_updated: string;
}

// API 响应接口
export interface ProfileResponse {
    success: boolean;
    profile?: AbilityProfile;
    generated_at?: string;
    message?: string;
}

/**
 * 获取综合能力画像（从数据库读取）
 */
export async function getOverallProfile(): Promise<ProfileResponse> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/profile/overall`, {
            headers: { ...authHeaders(), }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('获取能力画像失败:', error);
        return {
            success: false,
            message: '网络错误，请稍后重试'
        };
    }
}

/**
 * 生成综合能力画像（手动触发）
 */
export async function generateProfile(apiConfig?: any): Promise<ProfileResponse> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/profile/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders(),
            },
            body: apiConfig ? JSON.stringify({
                user_id: getUserId(),
                api_config: apiConfig
            }) : undefined
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('生成能力画像失败:', error);
        return {
            success: false,
            message: '网络错误，请稍后重试'
        };
    }
}

/**
 * 获取单个会话的能力画像
 */
export async function getSessionProfile(sessionId: string): Promise<ProfileResponse> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/profile/session/${sessionId}`, {
            headers: { ...authHeaders(), }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('获取会话画像失败:', error);
        return {
            success: false,
            message: '网络错误，请稍后重试'
        };
    }
}

export async function getSessionScores(sessionId: string): Promise<{ success: boolean; scores: any[] }> {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/scores`, {
        headers: authHeaders(),
    });
    if (!response.ok) throw new Error('获取评分失败');
    return response.json();
}

export async function generateSessionReport(sessionId: string): Promise<{ markdown: string; pdf_url: string }> {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/report`, {
        method: 'POST',
        headers: authHeaders(),
    });
    if (!response.ok) throw new Error('生成面评报告失败');
    return response.json();
}