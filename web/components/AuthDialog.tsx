"use client";

import { useState } from "react";
import { Loader2, Smartphone, LockKeyhole, ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { sendCode, register, login } from "@/lib/api/auth";
import { saveAuth } from "@/lib/auth";

interface AuthDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSuccess: (phone: string, nickname?: string, avatar?: string) => void;
}

export function AuthDialog({ open, onOpenChange, onSuccess }: AuthDialogProps) {
    const [mode, setMode] = useState<"login" | "register">("login");
    const [phone, setPhone] = useState("");
    const [password, setPassword] = useState("");
    const [code, setCode] = useState("");
    const [debugCode, setDebugCode] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const resetForm = () => {
        setPassword("");
        setCode("");
        setDebugCode("");
        setError("");
    };

    const handleModeChange = (value: string) => {
        setMode(value as "login" | "register");
        resetForm();
    };

    const handleSendCode = async () => {
        setError("");
        setDebugCode("");
        if (!/^1\d{10}$/.test(phone)) {
            setError("请输入正确的11位手机号");
            return;
        }
        setLoading(true);
        try {
            const res = await sendCode(phone);
            if (res.debug_code) {
                setDebugCode(`验证码已发送：${res.debug_code}（演示环境直接展示，无需短信）`);
            }
        } catch (e: any) {
            setError(e.message || "验证码发送失败");
        } finally {
            setLoading(false);
        }
    };

    const handleLogin = async () => {
        setError("");
        if (!/^1\d{10}$/.test(phone)) {
            setError("请输入正确的11位手机号");
            return;
        }
        if (!password) {
            setError("请输入密码");
            return;
        }
        setLoading(true);
        try {
            const res = await login(phone, password);
            saveAuth(res.token, res.phone, res.nickname || '', res.avatar || 'teal');
            onSuccess(res.phone, res.nickname || '', res.avatar || 'teal');
            resetForm();
        } catch (e: any) {
            setError(e.message || "登录失败");
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async () => {
        setError("");
        if (!/^1\d{10}$/.test(phone)) {
            setError("请输入正确的11位手机号");
            return;
        }
        if (!code) {
            setError("请输入验证码");
            return;
        }
        if (password.length < 6) {
            setError("密码至少6位");
            return;
        }
        setLoading(true);
        try {
            const res = await register(phone, code, password);
            saveAuth(res.token, res.phone, res.nickname || '', res.avatar || 'teal');
            onSuccess(res.phone, res.nickname || '', res.avatar || 'teal');
            resetForm();
        } catch (e: any) {
            setError(e.message || "注册失败");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-center text-xl">欢迎使用职面 AI</DialogTitle>
                    <DialogDescription className="text-center">
                        登录后即可开始模拟面试与简历诊断
                    </DialogDescription>
                </DialogHeader>

                <Tabs value={mode} onValueChange={handleModeChange} className="w-full">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="login">登录</TabsTrigger>
                        <TabsTrigger value="register">注册</TabsTrigger>
                    </TabsList>

                    <TabsContent value="login" className="space-y-3 pt-4">
                        <div className="relative">
                            <Smartphone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input className="pl-9" placeholder="手机号" value={phone} onChange={(e) => setPhone(e.target.value)} />
                        </div>
                        <div className="relative">
                            <LockKeyhole className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input className="pl-9" type="password" placeholder="密码" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleLogin()} />
                        </div>
                        {error && <div className="text-sm text-red-600">{error}</div>}
                        <Button onClick={handleLogin} disabled={loading} className="w-full bg-teal-600 hover:bg-teal-700">
                            {loading && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
                            登录
                        </Button>
                    </TabsContent>

                    <TabsContent value="register" className="space-y-3 pt-4">
                        <div className="relative">
                            <Smartphone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input className="pl-9" placeholder="手机号" value={phone} onChange={(e) => setPhone(e.target.value)} />
                        </div>
                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                <Input className="pl-9" placeholder="验证码" value={code} onChange={(e) => setCode(e.target.value)} />
                            </div>
                            <Button variant="outline" onClick={handleSendCode} disabled={loading} className="shrink-0">
                                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "获取验证码"}
                            </Button>
                        </div>
                        {debugCode && <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">{debugCode}</div>}
                        <div className="relative">
                            <LockKeyhole className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input className="pl-9" type="password" placeholder="设置密码（至少6位）" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleRegister()} />
                        </div>
                        {error && <div className="text-sm text-red-600">{error}</div>}
                        <Button onClick={handleRegister} disabled={loading} className="w-full bg-teal-600 hover:bg-teal-700">
                            {loading && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
                            注册并登录
                        </Button>
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    );
}
