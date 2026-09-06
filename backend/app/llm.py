"""共享 LLM 调用封装：流水线每个阶段都用它，任何失败都静默降级、不阻断流水线。

设计目标：
- 全链路（清洗字幕 → 结构化 → 富化洞察 → 趋势解读 → 摘要/教练建议）都走 LLM，
  但 LLM 不可用时（没配 key / 网关挂了）流水线仍能出报告，只是叙事类字段留空。
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


async def complete(system: str, user: str) -> str:
    """纯文本补全。任何失败都返回空串。"""
    if not ready():
        return ""
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", user)])
    try:
        resp = await (prompt | _chat()).ainvoke({})
        text = getattr(resp, "content", None)
        return (text or "").strip() if isinstance(text, str) else str(resp).strip()
    except Exception:
        return ""


async def complete_json(system: str, user: str, schema: type[T]) -> T | None:
    """结构化输出：优先 function calling，失败降级 JsonOutputParser，再失败返回 None。"""
    if not ready():
        return None
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", user)])
    llm = _chat()
    try:
        chain = prompt | llm.with_structured_output(schema, method="function_calling")
        return await chain.ainvoke({})
    except Exception:
        pass
    try:
        parser = JsonOutputParser(pydantic_object=schema)
        raw = await (prompt | llm | parser).ainvoke({})
        return schema(**raw) if isinstance(raw, dict) else None
    except Exception:
        return None
