"""共享 LLM 调用封装：流水线每个阶段都用它，任何失败都静默降级、不阻断流水线。

设计目标：
- 全链路（清洗字幕 → 结构化 → 富化洞察 → 趋势解读 → 摘要/教练建议）都走 LLM，
  但 LLM 不可用时（没配 key / 网关挂了）流水线仍能出报告，只是叙事类字段留空。
- 统一接收 `skills.py` 里的 ChatPromptTemplate + 变量，避免 prompt 散落各处。
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


def ready() -> bool:
    return bool(get_settings().llm_api_key)


def _chat():
    from langchain_openai import ChatOpenAI

    s = get_settings()
    return ChatOpenAI(
        model=s.llm_model,
        api_key=s.llm_api_key,
        base_url=s.llm_base_url,
        temperature=0.3,
    )


async def run(prompt, **kwargs) -> str:
    """纯文本 skill：ChatPromptTemplate → 文本。任何失败都返回空串。"""
    if not ready():
        return ""
    try:
        resp = await (prompt | _chat()).ainvoke(kwargs)
        text = getattr(resp, "content", None)
        return (text or "").strip() if isinstance(text, str) else str(resp).strip()
    except Exception:
        return ""


async def run_structured(prompt, schema: type[T], **kwargs) -> T | None:
    """结构化 skill：优先 function calling，失败降级 JsonOutputParser，再失败返回 None。"""
    if not ready():
        return None
    from langchain_core.output_parsers import JsonOutputParser

    llm = _chat()
    try:
        chain = prompt | llm.with_structured_output(schema, method="function_calling")
        return await chain.ainvoke(kwargs)
    except Exception:
        pass
    try:
        parser = JsonOutputParser(pydantic_object=schema)
        raw = await (prompt | llm | parser).ainvoke(kwargs)
        return schema(**raw) if isinstance(raw, dict) else None
    except Exception:
        return None
