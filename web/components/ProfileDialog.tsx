"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Upload, UserRound } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { updateProfile, uploadAvatar } from "@/lib/api/auth";
import { toast } from "sonner";
import { clearAuth } from "@/lib/auth";
import { getUsageSummary, exportUserData, deleteAccount } from "@/lib/api/account";
import { cn } from "@/lib/utils";

const AVATAR_COLORS: { key: string; className: string }[] = [
    { key: 'teal', className: 'bg-teal-500' },
    { key: 'blue', className: 'bg-blue-500' },
    { key: 'purple', className: 'bg-purple-500' },
    { key: 'orange', className: 'bg-orange-500' },
    { key: 'green', className: 'bg-green-500' },
    { key: 'pink', className: 'bg-pink-500' },
];

function isImageAvatar(avatar: string): boolean {
    return avatar.startsWith('/') || avatar.startsWith('http');
}

interface ProfileDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    currentNickname: string;
    currentAvatar: string;
    onSave: (nickname: string, avatar: string) => void;
}

export function ProfileDialog({ open, onOpenChange, currentNickname, currentAvatar, onSave }: ProfileDialogProps) {
    const [nickname, setNickname] = useState(currentNickname || "");
    const [avatar, setAvatar] = useState(currentAvatar || "teal");
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [usage, setUsage] = useState<{ request_count: number; session_count: number; message_count: number; error_count: number } | null>(null);
    const [busy, setBusy] = useState("");
    const fileRef = useRef<HTMLInputElement>(null);
    useEffect(() => {
        if (!open) return;
        getUsageSummary().then((d) => setUsage(d.summary)).catch(() => setUsage(null));
    }, [open]);

    const displayAvatar = previewUrl || (isImageAvatar(avatar) ? avatar : null);
    const colorKey = isImageAvatar(avatar) ? "teal" : (avatar || "teal");

    const handleFile = (file: File | null) => {
        if (!file) return;
        if (!/\.(png|jpe?g|webp|gif)$/i.test(file.name)) {
            setError("仅支持 png/jpg/jpeg/webp/gif 图片");
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            setError("头像图片不能超过5MB");
            return;
        }
        setError("");
        setSelectedFile(file);
        setPreviewUrl(URL.createObjectURL(file));
    };


    const handleExport = async () => {
        setBusy("export");
        setError("");
        try {
            const data = await exportUserData();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "ai_interview_data.json";
            a.click();
            URL.revokeObjectURL(url);
            toast.success("数据已导出");
        } catch (e: any) {
            setError(e.message || "导出失败");
        } finally {
            setBusy("");
        }
    };

    const handleDelete = async () => {
        if (!window.confirm("确定删除账号和全部数据吗？该操作不可恢复。")) return;
        setBusy("delete");
        setError("");
        try {
            await deleteAccount();
            clearAuth();
            window.location.href = "/";
        } catch (e: any) {
            setError(e.message || "删除失败");
            setBusy("");
        }
    };    const handleSave = async () => {
        const name = nickname.trim();
        if (!name) {
            setError("请输入用户名");
            return;
        }
        setError("");
        setLoading(true);
        try {
            let finalAvatar = avatar;
            if (selectedFile) {
                const uploaded = await uploadAvatar(selectedFile);
                finalAvatar = uploaded.avatar;
            } else if (!isImageAvatar(avatar)) {
                finalAvatar = colorKey;
            }
            await updateProfile(name, finalAvatar);
            onSave(name, finalAvatar);
            onOpenChange(false);
        } catch (e: any) {
            setError(e.message || "保存失败");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-center text-xl">个人资料</DialogTitle>
                    <DialogDescription className="text-center">设置用户名和头像</DialogDescription>
                </DialogHeader>

                <div className="space-y-4 pt-2">
                    <div className="flex items-center gap-4">
                        <div className="relative shrink-0">
                            {displayAvatar ? (
                                <img src={displayAvatar} alt="头像" className="w-16 h-16 rounded-full object-cover border border-gray-200" />
                            ) : (
                                <div className={cn("w-16 h-16 rounded-full flex items-center justify-center text-2xl text-white font-bold", AVATAR_COLORS.find(c => c.key === colorKey)?.className || "bg-teal-500")}>
                                    {(nickname || "用").slice(0, 1).toUpperCase()}
                                </div>
                            )}
                            <button
                                onClick={() => fileRef.current?.click()}
                                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-gray-900 text-white flex items-center justify-center shadow"
                                title="上传头像"
                            >
                                <Upload className="w-3.5 h-3.5" />
                            </button>
                            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={(e) => handleFile(e.target.files?.[0] || null)} />
                        </div>
                        <div className="flex-1">
                            <label className="text-sm font-medium text-gray-700 block mb-1">用户名</label>
                            <div className="relative">
                                <UserRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                <Input className="pl-9" maxLength={20} placeholder="输入用户名" value={nickname} onChange={(e) => setNickname(e.target.value)} />
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">头像颜色（不上传图片时可选择）</label>
                        <div className="flex gap-3">
                            {AVATAR_COLORS.map((c) => (
                                <button
                                    key={c.key}
                                    onClick={() => { setAvatar(c.key); setPreviewUrl(null); setSelectedFile(null); }}
                                    className={cn(
                                        "w-10 h-10 rounded-full transition-all",
                                        c.className,
                                        !selectedFile && !isImageAvatar(avatar) && avatar === c.key ? "ring-4 ring-offset-2 ring-gray-300 scale-110" : "opacity-70 hover:opacity-100"
                                    )}
                                />
                            ))}
                        </div>
                    </div>

                    {error && <div className="text-sm text-red-600">{error}</div>}


                    <div className="rounded-xl border border-gray-200 p-3 space-y-2">
                        <div className="flex items-center justify-between text-sm">
                            <span className="font-medium text-gray-700">数据与用量</span>
                            {usage ? (
                                <span className="text-xs text-gray-500">{usage.session_count} 场面试 / {usage.message_count} 条消息 / {usage.request_count} 次请求</span>
                            ) : (
                                <span className="text-xs text-gray-400">加载中...</span>
                            )}
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <Button variant="outline" size="sm" onClick={handleExport} disabled={!!busy}>
                                {busy === "export" ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                                导出数据
                            </Button>
                            <Button variant="outline" size="sm" className="text-red-600 border-red-200 hover:bg-red-50" onClick={handleDelete} disabled={!!busy}>
                                {busy === "delete" ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                                注销账号
                            </Button>
                        </div>
                    </div>                    <Button onClick={handleSave} disabled={loading} className="w-full bg-teal-600 hover:bg-teal-700">
                        {loading && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
                        保存
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}