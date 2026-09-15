"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, Scale, ScrollText, XCircle } from "lucide-react";
import { API_BASE_URL, authHeaders } from "@/lib/api/config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Appeal {
    id: number;
    user_id: string;
    session_id: string;
    question_index: number;
    reason: string;
    status: string;
    original_total?: number;
    revised_total?: number;
    admin_note?: string;
    created_at: string;
}

interface AuditLog {
    id: number;
    user_id: string;
    action: string;
    target_type?: string;
    target_id?: string;
    detail?: unknown;
    created_at: string;
}

export default function ReviewAdminPage() {
    const [appeals, setAppeals] = useState<Appeal[]>([]);
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [scores, setScores] = useState<Record<number, string>>({});
    const [notes, setNotes] = useState<Record<number, string>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const [appealRes, logRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/admin/appeals?status=pending`, { headers: authHeaders() }),
                fetch(`${API_BASE_URL}/api/admin/audit-logs?limit=50`, { headers: authHeaders() }),
            ]);
            if (!appealRes.ok || !logRes.ok) throw new Error("加载失败，请确认当前账号是管理员");
            setAppeals((await appealRes.json()).appeals || []);
            setLogs((await logRes.json()).logs || []);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    async function decide(id: number, status: "resolved" | "rejected") {
        const revised = scores[id] ? Number(scores[id]) : null;
        const res = await fetch(`${API_BASE_URL}/api/admin/appeals/${id}/decide`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeaders() },
            body: JSON.stringify({ revised_total: revised, admin_note: notes[id] || "", status }),
        });
        if (!res.ok) { alert("处理失败"); return; }
        setAppeals(prev => prev.filter(a => a.id !== id));
    }

    return (
        <main className="min-h-screen bg-slate-50 px-6 py-8">
            <div className="max-w-6xl mx-auto space-y-6">
                <div className="flex items-center justify-between">
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Scale className="w-6 h-6 text-teal-600" /> 评分复核后台
                    </h1>
                    <Button variant="outline" onClick={load} disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} /> 刷新
                    </Button>
                </div>

                {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-base">待处理申诉（{appeals.length}）</CardTitle></CardHeader>
                    <CardContent className="space-y-4">
                        {appeals.length === 0 && <p className="text-sm text-slate-500 py-4 text-center">暂无待处理申诉</p>}
                        {appeals.map(a => (
                            <div key={a.id} className="border rounded-lg p-4 space-y-3">
                                <div className="text-sm text-slate-700">
                                    <span className="font-medium">会话 {a.session_id.slice(0, 8)}</span> · 第 {a.question_index + 1} 题 · 原分 {a.original_total ?? "-"}
                                </div>
                                <p className="text-sm text-slate-600">申诉理由：{a.reason}</p>
                                <div className="flex flex-wrap gap-2">
                                    <input value={scores[a.id] || ""} onChange={e => setScores({ ...scores, [a.id]: e.target.value })}
                                        placeholder="复核分数 0-10（可选）" className="w-40 rounded-lg border px-3 py-2 text-sm" />
                                    <input value={notes[a.id] || ""} onChange={e => setNotes({ ...notes, [a.id]: e.target.value })}
                                        placeholder="复核备注" className="flex-1 min-w-[200px] rounded-lg border px-3 py-2 text-sm" />
                                    <Button onClick={() => decide(a.id, "resolved")} className="bg-teal-600 hover:bg-teal-700">
                                        <CheckCircle2 className="w-4 h-4 mr-1" /> 通过并改分
                                    </Button>
                                    <Button variant="outline" onClick={() => decide(a.id, "rejected")}>
                                        <XCircle className="w-4 h-4 mr-1" /> 驳回
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><ScrollText className="w-4 h-4" /> 审计日志</CardTitle></CardHeader>
                    <CardContent>
                        <div className="space-y-2 text-sm">
                            {logs.map(log => (
                                <div key={log.id} className="flex justify-between border-b last:border-0 py-2">
                                    <span className="text-slate-700">{log.action} · {log.target_type} {log.target_id}</span>
                                    <span className="text-slate-400">{new Date(log.created_at).toLocaleString()}</span>
                                </div>
                            ))}
                            {logs.length === 0 && <p className="text-slate-500 text-center py-3">暂无审计记录</p>}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </main>
    );
}
