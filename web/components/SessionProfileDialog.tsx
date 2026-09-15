'use client';

import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, X, Brain, CheckCircle2, Check, AlertCircle } from 'lucide-react';
import { getSessionProfile, getSessionScores, generateSessionReport, type AbilityProfile } from '@/lib/api/profile';
import { AbilityRadarChart } from './RadarChart';
import { API_BASE_URL, authHeaders } from '@/lib/api/config';
import { SkillTags } from './SkillTags';
import { Button } from './ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog';

interface Props {
    sessionId: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function SessionProfileDialog({ sessionId, open, onOpenChange }: Props) {
    const [profile, setProfile] = useState<AbilityProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [scores, setScores] = useState<any[]>([]);
    const [feedbackRating, setFeedbackRating] = useState(0);
    const [feedbackComment, setFeedbackComment] = useState("");
    const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
    const [submittingFeedback, setSubmittingFeedback] = useState(false);
    const [appealOpen, setAppealOpen] = useState<number | null>(null);
    const [appealReason, setAppealReason] = useState("");
    const [appealSubmitting, setAppealSubmitting] = useState(false);
    const [appealSubmitted, setAppealSubmitted] = useState<number[]>([]);

    useEffect(() => {
        if (open && sessionId) {
            loadProfile();
        }
    }, [open, sessionId]);

    useEffect(() => {
        if (!open || !generating) return;
        const timer = setInterval(loadProfile, 4000);
        return () => clearInterval(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, generating]);
    async function loadProfile() {
        setLoading(true);
        const response = await getSessionProfile(sessionId);
        try {
            const scoreResp = await getSessionScores(sessionId);
            setScores(scoreResp.scores || []);
        } catch {
            setScores([]);
        }

        if (response.success && response.profile) {
            setProfile(response.profile);
            setGenerating(false);
        } else {
            setProfile(null);
            setGenerating(true); // 画像正在生成中
        }
        setLoading(false);
    }

    async function handleDownloadReport() {
        try {
            const report = await generateSessionReport(sessionId);
            window.open(`${API_BASE_URL}${report.pdf_url}`, '_blank');
        } catch {
            alert('生成面评报告失败，请稍后重试');
        }
    }

    async function handleSubmitFeedback() {
        if (!feedbackRating || submittingFeedback) return;
        setSubmittingFeedback(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders(),
                },
                body: JSON.stringify({
                    target_type: 'report',
                    target_id: sessionId,
                    session_id: sessionId,
                    rating: feedbackRating,
                    tags: [],
                    comment: feedbackComment,
                }),
            });
            if (!response.ok) throw new Error('反馈提交失败');
            setFeedbackSubmitted(true);
        } catch {
            alert('反馈提交失败，请稍后重试');
        } finally {
            setSubmittingFeedback(false);
        }
    }

    async function handleSubmitAppeal(questionIndex: number) {
        if (appealReason.trim().length < 2 || appealSubmitting) return;
        setAppealSubmitting(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/appeals`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders(),
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    question_index: questionIndex,
                    reason: appealReason.trim(),
                }),
            });
            if (!response.ok) throw new Error('申诉提交失败');
            setAppealSubmitted((current) => [...current, questionIndex]);
            setAppealOpen(null);
            setAppealReason("");
        } catch {
            alert('申诉提交失败，请稍后重试');
        } finally {
            setAppealSubmitting(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Brain className="w-5 h-5 text-teal-600" />
                        本轮面试能力评估
                    </DialogTitle>
                </DialogHeader>

                {/* 加载状态 */}
                {loading && (
                    <div className="flex flex-col items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 text-teal-600 animate-spin mb-4" />
                        <p className="text-sm text-gray-500">加载中...</p>
                    </div>
                )}

                {/* 生成中状态 */}
                {!loading && generating && (
                    <div className="flex flex-col items-center justify-center py-20 px-6">
                        <div className="w-16 h-16 bg-teal-50 rounded-full flex items-center justify-center mb-4">
                            <Loader2 className="w-8 h-8 text-teal-600 animate-spin" />
                        </div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">画像生成中</h3>
                        <p className="text-sm text-gray-500 text-center mb-6 max-w-sm">
                            AI 正在分析您的面试表现，请稍等片刻...
                        </p>
                        <Button
                            onClick={loadProfile}
                            variant="outline"
                            className="flex items-center gap-2"
                        >
                            <RefreshCw className="w-4 h-4" />
                            刷新
                        </Button>
                    </div>
                )}

                {/* 有数据 - 显示画像 */}
                {!loading && !generating && profile && (
                    <div className="space-y-6">
                        {/* 用户真实感受评价：进入优化闭环 */}
                        <div className="bg-white border border-gray-200 rounded-xl p-6">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-base font-semibold text-gray-900">这次评估对你有帮助吗？</h3>
                                {feedbackSubmitted && (
                                    <span className="text-xs text-green-600 flex items-center gap-1">
                                        <Check className="w-3 h-3" /> 已提交，感谢反馈
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-2 mb-3">
                                {[1, 2, 3, 4, 5].map((star) => (
                                    <button
                                        key={star}
                                        type="button"
                                        disabled={feedbackSubmitted}
                                        onClick={() => setFeedbackRating(star)}
                                        className={`text-2xl transition-transform hover:scale-110 ${
                                            star <= feedbackRating ? 'text-amber-400' : 'text-gray-300'
                                        }`}
                                        aria-label={`${star} 星`}
                                    >
                                        ★
                                    </button>
                                ))}
                                <span className="text-xs text-gray-400 ml-1">
                                    {feedbackRating ? `${feedbackRating} 星` : '点击评分'}
                                </span>
                            </div>
                            {!feedbackSubmitted && (
                                <div className="flex gap-2">
                                    <input
                                        value={feedbackComment}
                                        onChange={(e) => setFeedbackComment(e.target.value)}
                                        placeholder="哪里好用、哪里不准，写一句就行（可选）"
                                        className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
                                    />
                                    <Button
                                        size="sm"
                                        onClick={handleSubmitFeedback}
                                        disabled={!feedbackRating || submittingFeedback}
                                        className="bg-teal-600 hover:bg-teal-700 text-white"
                                    >
                                        {submittingFeedback ? <Loader2 className="w-4 h-4 animate-spin" /> : '提交反馈'}
                                    </Button>
                                </div>
                            )}
                        </div>

                        {/* 逐题评分 + 报告下载 */}
                        {scores.length > 0 && (
                            <div className="bg-white border border-gray-200 rounded-xl p-6">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-base font-semibold text-gray-900">逐题评分</h3>
                                    <Button onClick={handleDownloadReport} variant="outline" size="sm">
                                        下载面评报告
                                    </Button>
                                </div>
                                <div className="space-y-3">
                                    {scores.map((s, idx) => (
                                        <div key={idx} className="border-b border-gray-100 pb-3 last:border-0">
                                            <div className="flex items-center justify-between">
                                                <span className="text-sm font-medium text-gray-800">第 {idx + 1} 题 · {s.total} 分</span>
                                                <span className="text-xs text-gray-500">
                                                    {Object.entries(s.dimensions || {}).map(([k, v]) => `${k}: ${v}`).join(' · ')}
                                                </span>
                                            </div>
                                            <p className="text-sm text-gray-600 mt-1 line-clamp-2">{s.comment}</p>
                                            <div className="mt-2">
                                                {appealSubmitted.includes(idx) ? (
                                                    <span className="text-xs text-green-600 flex items-center gap-1">
                                                        <Check className="w-3 h-3" /> 已申请人工复核
                                                    </span>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setAppealOpen(appealOpen === idx ? null : idx);
                                                            setAppealReason("");
                                                        }}
                                                        className="text-xs text-teal-600 hover:text-teal-700 flex items-center gap-1"
                                                    >
                                                        <AlertCircle className="w-3 h-3" /> 对本评分申请复核
                                                    </button>
                                                )}
                                            </div>
                                            {appealOpen === idx && !appealSubmitted.includes(idx) && (
                                                <div className="mt-2 flex gap-2">
                                                    <input
                                                        value={appealReason}
                                                        onChange={(e) => setAppealReason(e.target.value)}
                                                        placeholder="请说明你认为评分不合理的原因"
                                                        className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
                                                    />
                                                    <Button
                                                        size="sm"
                                                        disabled={appealReason.trim().length < 2 || appealSubmitting}
                                                        onClick={() => handleSubmitAppeal(idx)}
                                                        className="bg-teal-600 hover:bg-teal-700 text-white"
                                                    >
                                                        {appealSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : '提交申诉'}
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {/* 雷达图 */}
                        <div className="bg-gray-50 rounded-xl p-6">
                            <h3 className="text-base font-semibold text-gray-900 mb-4">能力雷达图</h3>
                            <AbilityRadarChart data={profile} />
                        </div>

                        {/* 技能标签 */}
                        {profile.skill_tags && profile.skill_tags.length > 0 && (
                            <div className="bg-blue-50 rounded-xl p-6">
                                <SkillTags tags={profile.skill_tags} />
                            </div>
                        )}

                        {/* 综合评价 */}
                        {profile.overall_assessment && (
                            <div className="bg-purple-50 rounded-xl p-6">
                                <h3 className="text-base font-semibold text-gray-900 mb-3">综合评价</h3>
                                <p className="text-sm text-gray-700 leading-relaxed">
                                    {profile.overall_assessment}
                                </p>
                            </div>
                        )}

                        {/* 优势和不足 */}
                        {(profile.key_strengths && profile.key_strengths.length > 0 ||
                            profile.key_weaknesses && profile.key_weaknesses.length > 0) && (
                                <div className="grid grid-cols-2 gap-4">
                                    {profile.key_strengths && profile.key_strengths.length > 0 && (
                                        <div className="bg-emerald-50 rounded-xl p-6">
                                            <h3 className="text-base font-semibold text-gray-900 mb-3">主要优势</h3>
                                            <ul className="space-y-2">
                                                {profile.key_strengths.map((strength, index) => (
                                                    <li key={index} className="text-sm text-gray-700 flex items-start gap-2">
                                                        <span className="text-teal-600 mt-0.5">✓</span>
                                                        <span>{strength}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                    {profile.key_weaknesses && profile.key_weaknesses.length > 0 && (
                                        <div className="bg-orange-50 rounded-xl p-6">
                                            <h3 className="text-base font-semibold text-gray-900 mb-3">待提升项</h3>
                                            <ul className="space-y-2">
                                                {profile.key_weaknesses.map((weakness, index) => (
                                                    <li key={index} className="text-sm text-gray-700 flex items-start gap-2">
                                                        <span className="text-amber-600 mt-0.5">△</span>
                                                        <span>{weakness}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            )}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
