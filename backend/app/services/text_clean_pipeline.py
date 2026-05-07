"""
文本清洗唯一入口：全角转半角、去零宽、控制字符、空白规范化、小写化。
各 Agent 禁止重复实现清洗逻辑，统一从黑板读取 cleaned_text / preprocessed_content。
"""

from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """文本清洗：全角转半角、去零宽、去控制字符（保留 \\n\\r）、空白规范化、小写化。"""
    s = str(text or "")
    result: list[str] = []
    for ch in s:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(" ")
        else:
            result.append(ch)
    s = "".join(result)

    s = re.sub(r"[\u200B-\u200F\uFEFF]", "", s)
    s = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.lower().strip()
