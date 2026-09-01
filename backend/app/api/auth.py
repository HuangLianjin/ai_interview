"""用户认证：手机验证码注册、登录、JWT 令牌、个人资料。

令牌有效期默认 30 分钟，可通过 TOKEN_TTL_SECONDS 环境变量调整。
"""
import hashlib
import hmac
import os
import secrets
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..database.base import db_manager
from ..services.security import check_rate_limit, clear_login_failures, is_login_locked, record_login_failure

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-me")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "1800"))
CODE_TTL_MINUTES = int(os.getenv("CODE_TTL_MINUTES", "5"))
DEFAULT_AVATAR = "teal"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"pbkdf2${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(computed.hex(), digest)


def create_token(user_id: int, phone: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "phone": phone,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def require_auth(authorization: str = Header(default=None, alias="Authorization")):
    """FastAPI 依赖：校验 Bearer 令牌，返回 payload。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期，请重新登录")
    payload = decode_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或登录已过期，请重新登录")
    return payload


class SendCodeRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    code: str = Field(..., min_length=4, max_length=10)
    password: str = Field(..., min_length=6, max_length=64)


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    password: str = Field(..., min_length=1, max_length=64)


class ProfileUpdateRequest(BaseModel):
    nickname: str = Field(default="", max_length=20)
    avatar: str = Field(default=DEFAULT_AVATAR, max_length=512)


def _validate_phone(phone: str):
    if not phone.isdigit() or len(phone) != 11 or not phone.startswith("1"):
        raise HTTPException(status_code=400, detail="请输入正确的11位手机号")


async def _get_user_by_phone(phone: str):
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, phone, password_hash, nickname, avatar, created_at FROM users WHERE phone = $1",
            phone,
        )
        return dict(row) if row else None


async def _get_user_by_id(user_id: int):
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, phone, nickname, avatar, created_at FROM users WHERE id = $1",
            user_id,
        )
        return dict(row) if row else None


@router.post("/send-code")
async def send_code(req: SendCodeRequest):
    _validate_phone(req.phone)
    check_rate_limit(f"send_code:{req.phone}", 5, 60)
    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)
    async with db_manager.get_connection() as conn:
        await conn.execute(
            "UPDATE sms_codes SET used = TRUE WHERE phone = $1 AND used = FALSE",
            req.phone,
        )
        await conn.execute(
            "INSERT INTO sms_codes (phone, code, used, expires_at, created_at) VALUES ($1, $2, FALSE, $3, $4)",
            req.phone, code, expires_at, now,
        )
    # 演示环境：未接短信服务商时直接返回验证码，方便本地/面试演示
    return {
        "success": True,
        "message": "验证码已发送",
        "debug_code": code,
        "expires_in": CODE_TTL_MINUTES * 60,
    }


@router.post("/register")
async def register(req: RegisterRequest):
    _validate_phone(req.phone)
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, code, used, expires_at FROM sms_codes "
            "WHERE phone = $1 ORDER BY created_at DESC LIMIT 1",
            req.phone,
        )
        if not row or row["used"] or row["code"] != req.code:
            raise HTTPException(status_code=400, detail="验证码错误")
        if row["expires_at"] < datetime.utcnow():
            raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")

        exists = await conn.fetchval("SELECT 1 FROM users WHERE phone = $1", req.phone)
        if exists:
            raise HTTPException(status_code=400, detail="该手机号已注册，请直接登录")

        user_id = await conn.fetchval(
            "INSERT INTO users (phone, password_hash, nickname, avatar, created_at, updated_at) "
            "VALUES ($1, $2, '', $3, $4, $4) RETURNING id",
            req.phone, hash_password(req.password), DEFAULT_AVATAR, datetime.utcnow(),
        )
        await conn.execute(
            "UPDATE sms_codes SET used = TRUE WHERE id = $1", row["id"],
        )
    token = create_token(user_id, req.phone)
    return {"success": True, "token": token, "phone": req.phone, "nickname": "", "avatar": DEFAULT_AVATAR}


@router.post("/login")
async def login(req: LoginRequest):
    _validate_phone(req.phone)
    locked, wait_seconds = await is_login_locked(req.phone)
    if locked:
        raise HTTPException(status_code=429, detail=f"登录失败次数过多，请 {max(1, (wait_seconds + 59) // 60)} 分钟后重试")
    user = await _get_user_by_phone(req.phone)
    if not user or not verify_password(req.password, user["password_hash"]):
        await record_login_failure(req.phone)
        raise HTTPException(status_code=400, detail="手机号或密码错误")
    await clear_login_failures(req.phone)
    token = create_token(user["id"], user["phone"])
    return {
        "success": True,
        "token": token,
        "phone": user["phone"],
        "nickname": user.get("nickname") or "",
        "avatar": user.get("avatar") or DEFAULT_AVATAR,
    }


@router.get("/me")
async def get_me(payload: dict = Depends(require_auth)):
    user = await _get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True, "phone": user["phone"], "nickname": user.get("nickname") or "", "avatar": user.get("avatar") or DEFAULT_AVATAR}


@router.put("/profile")
async def update_profile(req: ProfileUpdateRequest, payload: dict = Depends(require_auth)):
    nickname = req.nickname.strip()
    if len(nickname) > 20:
        raise HTTPException(status_code=400, detail="用户名不能超过20个字符")
    async with db_manager.get_connection() as conn:
        await conn.execute(
            "UPDATE users SET nickname = $1, avatar = $2, updated_at = $3 WHERE id = $4",
            nickname, req.avatar, datetime.utcnow(), int(payload["sub"]),
        )
    return {"success": True, "nickname": nickname, "avatar": req.avatar}

ALLOWED_AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), payload: dict = Depends(require_auth)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 png/jpg/jpeg/webp/gif 图片")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像图片不能超过5MB")
    avatar_dir = Path("static") / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    (avatar_dir / fname).write_bytes(data)
    avatar_path = f"/static/avatars/{fname}"
    async with db_manager.get_connection() as conn:
        await conn.execute(
            "UPDATE users SET avatar = $1, updated_at = $2 WHERE id = $3",
            avatar_path, datetime.utcnow(), int(payload["sub"]),
        )
    return {"success": True, "avatar": avatar_path}
