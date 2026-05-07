from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .settings_bridge import settings


PROMPTS_DIR = Path(settings.PROJECT_ROOT) / "prompts"


class IntentAnalystResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    intent_labels: list[str] = Field(alias="意图标签", min_length=1)
    suggested_units: list[str] = Field(alias="建议激活单元")
    keywords: list[str] = Field(alias="关键词")
    summary: str = Field(alias="简述", min_length=1)


class WorkUnitResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conclusion: str = Field(alias="结论", min_length=1)
    severity: str = Field(alias="严重程度", min_length=1)
    confidence: str = Field(alias="置信度", min_length=1)
    evidence: list[dict[str, Any]] = Field(alias="证据", default_factory=list)
    self_check: dict[str, Any] = Field(alias="自我检查", default_factory=dict)
    reasoning: str = Field(alias="推理过程", min_length=1)


class ArbiterResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    final_decision: str = Field(alias="最终判定", min_length=1)
    action: str = Field(alias="执行动作", min_length=1)
    basis: str = Field(alias="判定依据", min_length=1)
    short_reason: str = Field(alias="简要理由", min_length=1)
    accepted_evidence: str = Field(alias="采纳的证据", min_length=1)
    rejected_claims: str = Field(alias="拒绝的主张", min_length=1)


def _read_prompt_template(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def _render_prompt(template: str, variables: dict[str, str]) -> str:
    prompt = template
    for key, value in variables.items():
        prompt = prompt.replace("{" + key + "}", str(value))
    return prompt


def _create_openai_client() -> OpenAI:
    if not settings.OPENAI_API_KEY.strip():
        raise RuntimeError("OPENAI_API_KEY 未配置")
    return OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


def _safe_parse_json_object(text: str) -> dict[str, Any]:
    content = str(text or "").strip()
    if not content:
        raise ValueError("LLM 返回为空")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM 返回不是合法 JSON 对象")
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM 返回不是 JSON 对象")
    return parsed


def _safe_parse_json_array(text: str) -> list[Any]:
    content = str(text or "").strip()
    if not content:
        raise ValueError("LLM 返回为空")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("[")
        end = content.rfind("]")
        if start < 0 or end <= start:
            raise ValueError("LLM 返回不是合法 JSON 数组")
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, list):
        raise ValueError("LLM 返回不是 JSON 数组")
    return parsed


def _call_json_object(prompt: str, *, temperature: float = 0.0) -> dict[str, Any]:
    client = _create_openai_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "你必须只返回一个 JSON 对象，不要输出任何额外文本。",
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw = response.choices[0].message.content or ""
    return _safe_parse_json_object(raw)


def _call_json_array(prompt: str, *, temperature: float = 0.0) -> list[Any]:
    client = _create_openai_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": (
                    "你必须只返回 JSON 数组，不要输出任何额外文本。"
                    "如果无质疑，返回 []。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw = response.choices[0].message.content or ""
    return _safe_parse_json_array(raw)


def call_intent_analyst(content: str, *, temperature: float = 0.0) -> dict[str, Any]:
    """
    读取 prompts/intent_analyst.txt，替换 {content} 后调用 OpenAI，
    仅接受 JSON 输出，并通过 Pydantic（中文键名）校验后返回字典。
    """
    template = _read_prompt_template("intent_analyst.txt")
    prompt = _render_prompt(template, {"content": content})
    payload = _call_json_object(prompt, temperature=temperature)

    try:
        validated = IntentAnalystResult.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"意图分析 JSON 字段不符合预期: {exc}") from exc
    return validated.model_dump(by_alias=True)


def call_work_unit_politics(
    content: str,
    intent_info: str | dict[str, Any],
    *,
    temperature: float = 0.0,
) -> dict[str, Any]:
    template = _read_prompt_template("work_unit_politics.txt")
    intent_info_text = (
        json.dumps(intent_info, ensure_ascii=False) if isinstance(intent_info, dict) else str(intent_info)
    )
    prompt = _render_prompt(
        template,
        {
            "content": content,
            "intent_info": intent_info_text,
        },
    )
    payload = _call_json_object(prompt, temperature=temperature)
    try:
        validated = WorkUnitResult.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"工作单元 JSON 字段不符合预期: {exc}") from exc
    return validated.model_dump(by_alias=True)


def call_verifier(
    original_content: str,
    work_unit_finding: str | dict[str, Any],
    other_findings: str | list[Any] | None = None,
    *,
    temperature: float = 0.0,
) -> list[dict[str, Any]]:
    template = _read_prompt_template("verifier.txt")
    work_unit_text = (
        json.dumps(work_unit_finding, ensure_ascii=False)
        if isinstance(work_unit_finding, dict)
        else str(work_unit_finding)
    )
    if isinstance(other_findings, (dict, list)):
        other_findings_text = json.dumps(other_findings, ensure_ascii=False)
    else:
        other_findings_text = str(other_findings or "[]")
    prompt = _render_prompt(
        template,
        {
            "original_content": original_content,
            "work_unit_finding": work_unit_text,
            "other_findings": other_findings_text,
        },
    )
    result = _call_json_array(prompt, temperature=temperature)
    return [item for item in result if isinstance(item, dict)]


def call_arbiter(
    finding: str | dict[str, Any],
    challenges: str | list[Any],
    responses: str | list[Any],
    other_findings: str | list[Any],
    strategy: str = "安全优先",
    *,
    temperature: float = 0.0,
) -> dict[str, Any]:
    template = _read_prompt_template("arbiter.txt")
    prompt = _render_prompt(
        template,
        {
            "finding": json.dumps(finding, ensure_ascii=False) if isinstance(finding, dict) else str(finding),
            "challenges": json.dumps(challenges, ensure_ascii=False)
            if isinstance(challenges, list)
            else str(challenges),
            "responses": json.dumps(responses, ensure_ascii=False)
            if isinstance(responses, list)
            else str(responses),
            "other_findings": json.dumps(other_findings, ensure_ascii=False)
            if isinstance(other_findings, list)
            else str(other_findings),
            "strategy": strategy,
        },
    )
    payload = _call_json_object(prompt, temperature=temperature)
    try:
        validated = ArbiterResult.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"仲裁结果 JSON 字段不符合预期: {exc}") from exc
    return validated.model_dump(by_alias=True)

