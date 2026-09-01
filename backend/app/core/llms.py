"""LLM 创建与通道选择。

优先使用前端传入的 API 配置；前端未配置时回退到服务端环境变量，
方便私有部署直接使用 DeepSeek，无需用户在页面填写。
"""
import os
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def create_llm_from_config(
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 8000
) -> ChatOpenAI:
    """根据配置创建 LLM 实例。"""
    return ChatOpenAI(
        temperature=temperature,
        max_tokens=max_tokens,
        model_name=model,
        api_key=api_key,
        base_url=base_url
    )


def _server_config(channel: str) -> Optional[dict]:
    """读取服务端环境变量配置；未配置时返回 None。"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    if channel == "fast":
        model = os.getenv("FAST_MODEL", "").strip() or DEFAULT_MODEL
    else:
        model = os.getenv("SMART_MODEL", "").strip() or DEFAULT_MODEL
    return {"api_key": api_key, "base_url": base_url, "model": model}


def get_llm_for_request(api_config: Optional[dict] = None, channel: str = "smart") -> ChatOpenAI:
    """获取用于处理请求的 LLM 实例。

    优先使用前端传入的 api_config；缺失或 api_key 为空时回退到服务端
    OPENAI_API_KEY / OPENAI_BASE_URL / SMART_MODEL / FAST_MODEL。
    """
    if api_config:
        channel_config = api_config.get(channel)
        if channel_config and channel_config.get("api_key"):
            return create_llm_from_config(
                api_key=channel_config["api_key"],
                base_url=channel_config["base_url"],
                model=channel_config["model"],
                max_tokens=8000
            )

    server = _server_config(channel)
    if server:
        return create_llm_from_config(
            api_key=server["api_key"],
            base_url=server["base_url"],
            model=server["model"],
            max_tokens=8000
        )

    raise ValueError(
        "未配置大模型 API。可在前端设置中配置，或在服务端环境变量 OPENAI_API_KEY 中配置。"
    )


def get_async_omni_client(voice_config: Optional[dict] = None):
    """创建异步 OpenAI 客户端（用于流式语音模型）。

    优先使用前端传入的 voice_config；缺失时回退到 VOICE_API_KEY 等环境变量。
    """
    if not voice_config or not voice_config.get("api_key"):
        api_key = os.getenv("VOICE_API_KEY", "").strip()
        base_url = os.getenv("VOICE_BASE_URL", "").strip()
        model = os.getenv("VOICE_MODEL", "").strip()
        if api_key and base_url and model:
            voice_config = {"api_key": api_key, "base_url": base_url, "model": model}

    if not voice_config or not voice_config.get("api_key"):
        raise ValueError("未检测到语音模型 API 配置")

    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=voice_config["api_key"],
        base_url=voice_config["base_url"],
    )

def get_async_chat_client(api_config: Optional[dict] = None, channel: str = "smart"):
    """返回 (AsyncOpenAI, model)：供需要原始调用、不触发 LangGraph 流事件的场景使用。"""
    from openai import AsyncOpenAI

    api_key = None
    base_url = None
    model = None

    if api_config:
        channel_config = api_config.get(channel)
        if channel_config and channel_config.get("api_key"):
            api_key = channel_config["api_key"]
            base_url = channel_config["base_url"]
            model = channel_config["model"]

    if not api_key:
        server = _server_config(channel)
        if server:
            api_key = server["api_key"]
            base_url = server["base_url"]
            model = server["model"]

    if not api_key:
        raise ValueError("未配置大模型 API")

    return AsyncOpenAI(api_key=api_key, base_url=base_url), model
