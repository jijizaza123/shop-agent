# ============================================================================
#  LLM 调用收口层 —— 复用 C:/Agent/llm_client.py 的模式
#  带重试/超时/异常兜底 + 工具注册表 + 工具循环
#  本项目差异:模型走 Agnes(OpenAI 兼容协议),环境变量读 key
# ============================================================================
import json
import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI
from openai import (
    APIStatusError, APIConnectionError, RateLimitError,
    InternalServerError, APITimeoutError,
)
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_BASE_URL = os.environ["AGNES_BASE_URL"]
_API_KEY = os.environ["AGNES_API_KEY"]
_MODEL = os.environ["AGNES_MODEL"]

logger = logging.getLogger("llm")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

_RETRYABLE = (APIConnectionError, RateLimitError, InternalServerError, APITimeoutError, APIStatusError)


def _make_client() -> OpenAI:
    return OpenAI(base_url=_BASE_URL, api_key=_API_KEY, timeout=30.0, max_retries=0)


class RobustLLMClient:
    """对外只暴露 chat() 和 safe_chat_text()。
    chat() 返回原始 resp(上层读 tool_calls);
    safe_chat_text() 永远返回字符串,网页 UI 永不崩。"""

    def __init__(self, model: str = _MODEL, max_attempts: int = 4, timeout: float = 30.0):
        self.model = model
        self.max_attempts = max_attempts
        self._client = _make_client()
        _retryer = retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(_RETRYABLE),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        self._create = _retryer(self._client.chat.completions.create)

    def chat(self, messages, tools=None, **kwargs):
        return self._create(model=self.model, messages=messages, tools=tools, **kwargs)

    def safe_chat_text(self, messages, tools=None, **kwargs) -> str:
        try:
            resp = self._create(model=self.model, messages=messages, tools=tools, **kwargs)
            return resp.choices[0].message.content
        except APIStatusError as e:
            return f"[LLM 调用失败 · HTTP {e.status_code}] {e}"
        except APIConnectionError as e:
            return f"[LLM 调用失败 · 连接不可达或超时] {e}"
        except Exception as e:
            return f"[LLM 调用失败 · 未知错误] {type(e).__name__}: {e}"


llm = RobustLLMClient()

# ============================================================================
#  工具注册表 + 工具循环(给 agent/graph.py 用)
# ============================================================================
_TOOL_IMPLS = {}
_TOOL_SCHEMAS = {}


def register_tool(name, impl_fn, schema):
    _TOOL_IMPLS[name] = impl_fn
    _TOOL_SCHEMAS[name] = schema


def make_tool_schemas(names):
    return [_TOOL_SCHEMAS[n] for n in names if n in _TOOL_SCHEMAS]


def ask(messages, tool_schemas=None, verbose=False, max_rounds=5):
    """跑一次完整的工具循环,返回 (最终答案, meta)。
    meta: used_tool / tool_names / latency_ms / tokens_in / tokens_out / fallback_used
    """
    start = time.perf_counter()
    used_tool = False
    tool_names = []
    tokens_in = tokens_out = 0
    fallback_used = False

    for _ in range(max_rounds):
        _t = tool_schemas or None
        resp = llm.chat(messages, tools=_t if _t else None)
        if resp.usage:
            tokens_in += resp.usage.prompt_tokens
            tokens_out += resp.usage.completion_tokens
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return (msg.content or ""), {
                "used_tool": used_tool, "tool_names": tool_names,
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "tokens_in": tokens_in, "tokens_out": tokens_out,
                "fallback_used": fallback_used,
            }

        for call in msg.tool_calls:
            used_tool = True
            fn_name = call.function.name
            tool_names.append(fn_name)
            args = json.loads(call.function.arguments) if call.function.arguments else {}
            if verbose:
                print(f"  [Agent 调用工具] {fn_name}  参数: {args}")
            impl = _TOOL_IMPLS.get(fn_name)
            if impl is None:
                result = f"(未知工具 {fn_name},未注册)"
                fallback_used = True
            else:
                try:
                    result = impl(**args)
                except Exception as e:
                    result = f"(工具 {fn_name} 执行失败:{e})"
                    fallback_used = True
            messages.append({"role": "assistant", "content": None, "tool_calls": msg.tool_calls})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    return "(超过最大轮数,未拿到最终答案)", {
        "used_tool": used_tool, "tool_names": tool_names,
        "latency_ms": int((time.perf_counter() - start) * 1000),
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "fallback_used": True,
    }
