"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, BarChart3, DollarSign, RefreshCw, Star, Timer, Users } from "lucide-react";
import { API_BASE_URL, authHeaders } from "@/lib/api/config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface TraceSummary {
    total_runs: number;
    success_rate: number;
    error_runs: number;
    avg_latency_ms: number;
    p95_latency_ms: number;
    total_tokens: number;
    nodes: Array<{
        node_name: string;
        status: string;
        avg_latency_ms: number;
        calls: number;
        tokens: number;
    }>;
}

interface ProductMetrics {
    sessions_total: number;
    sessions_completed: number;
    completion_rate: number;
    messages: number;
    resume_results: number;
    generated_resumes: number;
    feedback_total: number;
    feedback_avg_rating: number;
    feedback_low_rating: number;
    open_eval_failures: number;
}

function fmtPercent(value: number) {
    return `${Math.round((value || 0) * 100)}%`;
}

export default function DashboardPage() {
    const [summary, setSummary] = useState<TraceSummary | null>(null);
    const [metrics, setMetrics] = useState<ProductMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const [summaryRes, metricsRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/observability/summary?days=7`, { headers: authHeaders() }),
                fetch(`${API_BASE_URL}/api/observability/product-metrics?days=7`, { headers: authHeaders() }),
            ]);
            if (!summaryRes.ok || !metricsRes.ok) {
                throw new Error("看板数据加载失败，请确认已登录");
            }
            const summaryData = await summaryRes.json();
            const metricsData = await metricsRes.json();
            setSummary(summaryData.summary);
            setMetrics(metricsData.metrics);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return (
        <main className="min-h-screen bg-slate-50 px-6 py-8">
            <div className="max-w-6xl mx-auto space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                            <BarChart3 className="w-6 h-6 text-teal-600" />
                            运行看板
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">近 7 天 Agent 运行、成本与用户反馈</p>
                    </div>
                    <Button variant="outline" onClick={load} disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
                        刷新
                    </Button>
                </div>

                {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        {error}
                    </div>
                )}

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard icon={<Activity className="w-4 h-4 text-teal-600" />} label="运行次数" value={summary?.total_runs ?? 0} />
                    <MetricCard icon={<Timer className="w-4 h-4 text-blue-600" />} label="成功率" value={fmtPercent(summary?.success_rate ?? 0)} />
                    <MetricCard icon={<Timer className="w-4 h-4 text-indigo-600" />} label="P95 延迟" value={`${Math.round(summary?.p95_latency_ms ?? 0)} ms`} />
                    <MetricCard icon={<DollarSign className="w-4 h-4 text-amber-600" />} label="Token 总量" value={(summary?.total_tokens ?? 0).toLocaleString()} />
                    <MetricCard icon={<Users className="w-4 h-4 text-emerald-600" />} label="面试完成率" value={fmtPercent(metrics?.completion_rate ?? 0)} />
                    <MetricCard icon={<Star className="w-4 h-4 text-amber-500" />} label="平均评分" value={`${metrics?.feedback_avg_rating ?? 0} / 5`} />
                    <MetricCard icon={<AlertTriangle className="w-4 h-4 text-red-500" />} label="待修复评测失败" value={metrics?.open_eval_failures ?? 0} />
                    <MetricCard icon={<AlertTriangle className="w-4 h-4 text-orange-500" />} label="低分反馈" value={metrics?.feedback_low_rating ?? 0} />
                </div>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">节点耗时与调用</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {summary?.nodes?.length ? (
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-left text-slate-500 border-b">
                                            <th className="py-2">节点</th>
                                            <th className="py-2">状态</th>
                                            <th className="py-2">调用次数</th>
                                            <th className="py-2">平均耗时</th>
                                            <th className="py-2">Token</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {summary.nodes.map((node, idx) => (
                                            <tr key={`${node.node_name}-${node.status}-${idx}`} className="border-b last:border-0">
                                                <td className="py-2 font-medium text-slate-800">{node.node_name}</td>
                                                <td className={`py-2 ${node.status === "success" ? "text-emerald-600" : "text-red-600"}`}>{node.status}</td>
                                                <td className="py-2">{node.calls}</td>
                                                <td className="py-2">{Math.round(node.avg_latency_ms || 0)} ms</td>
                                                <td className="py-2">{(node.tokens || 0).toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <p className="text-sm text-slate-500 py-6 text-center">暂无运行数据，先跑一次面试再看。</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </main>
    );
}

function MetricCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
    return (
        <Card>
            <CardContent className="pt-5">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    {icon}
                    {label}
                </div>
                <div className="mt-2 text-xl font-bold text-slate-900 break-all">{value}</div>
            </CardContent>
        </Card>
    );
}
