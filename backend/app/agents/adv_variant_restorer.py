"""对抗侦探：确定性变体检测与还原（无 LLM）。"""

from __future__ import annotations

import re
from typing import List, Tuple

from .homophone_candidates import HOMOPHONE_CANDIDATES, PHRASE_HOMOPHONE_MAP


class VariantRestorer:
    """拼音/形近/符号/拼接/零宽等规则级检测与弱还原（与 LLM 初判互为补充）。"""

    # 强映射：更稳定的缩写/编码/符号替换，可视为强还原
    HOMOPHONE_MAP: dict[str, str] = {
        "zf": "政府",
        "zg": "中国",
        "zw": "中文",
        "tw": "台湾",
        "td": "台独",
        "mg": "美国",
        "rb": "日本",
        "hg": "韩国",
        "hk": "香港",
        "hs": "黄色",
        "sq": "色情",
        "xp": "性爱",
        "pb": "嫖娼",
        "my": "卖淫",
        "sl": "色狼",
        "sb": "傻逼",
        "cnm": "草泥马",
        "nm": "尼玛",
        "djb": "大鸡巴",
        "nt": "脑瘫",
        "zz": "智障",
        "wq": "武器",
        "fg": "法官",
        "94": "就是",
        "520": "我爱你",
        "1314": "一生一世",
        "748": "去死吧",
        "555": "呜呜呜",
    }

    VISUAL_SIMILAR_MAP: dict[str, str] = {
        "〇": "零",
        "０": "0",
        "⒐": "9",
        "①": "1",
        "②": "2",
        "③": "3",
        "丨": "|",
        "＠": "@",
        "＃": "#",
        "∕": "/",
        "﹣": "-",
        "－": "-",
        "：（": "(",
    }

    SYMBOL_REPLACE_MAP: dict[str, str] = {
        "•": ".",
        "·": ".",
        "｡": "。",
        "，": ",",
        "！": "!",
        "？": "?",
        "：": ":",
        "；": ";",
        "＠": "@",
        "（": "(",
        "）": ")",
        "—": "-",
        "／": "/",
        "＝": "=",
        "～": "~",
        "*": "",
        "#": "",
    }

    def __init__(self) -> None:
        self.detected_types: List[str] = []

    def restore(self, text: str) -> Tuple[str, List[str]]:
        self.detected_types = []
        result = text
        result = self._restore_phrase_homophones(result)
        result = self._restore_pinyin(result)
        result = self._restore_visual(result)
        result = self._restore_symbols(result)
        result = self._restore_concatenation(result)
        result = self._remove_invisible_chars(result)
        return result, list(dict.fromkeys(self.detected_types))

    def _restore_phrase_homophones(self, text: str) -> str:
        result = text
        found = False
        for phrase, cands in PHRASE_HOMOPHONE_MAP.items():
            if phrase in result:
                found = True
                result = result.replace(phrase, cands[0])
        if found:
            self.detected_types.append("汉字谐音规避表达")
        return result

    def _restore_pinyin(self, text: str) -> str:
        result = text
        found = False
        for pinyin, chinese in sorted(self.HOMOPHONE_MAP.items(), key=lambda x: -len(x[0])):
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(pinyin)}(?![a-zA-Z0-9])"
            if re.search(pattern, result, re.IGNORECASE):
                found = True
                result = re.sub(pattern, chinese, result, flags=re.IGNORECASE)
        if found:
            self.detected_types.append("拼音/缩写混淆")
        return result

    def _restore_visual(self, text: str) -> str:
        result = text
        found = False
        for fake, real in self.VISUAL_SIMILAR_MAP.items():
            if fake in result:
                found = True
                result = result.replace(fake, real)
        weird = re.findall(r"[氵讠钅饣纟礻][\u4e00-\u9fff]", result)
        if weird:
            found = True
            self.detected_types.append("偏旁拆分绕过")
        if found:
            self.detected_types.append("形近字替换")
        return result

    def _restore_symbols(self, text: str) -> str:
        result = text
        found = False
        for fake, real in self.SYMBOL_REPLACE_MAP.items():
            if fake in result:
                found = True
                result = result.replace(fake, real)
        if found:
            self.detected_types.append("符号替换")
        return result

    def _restore_concatenation(self, text: str) -> str:
        result = text
        found = False
        suspicious = re.sub(r"([\u4e00-\u9fff])[\s\-·•*]+([\u4e00-\u9fff])", r"\1\2", result)
        if suspicious != result:
            found = True
            result = suspicious
        suspicious2 = re.sub(r"([a-zA-Z0-9])[\s\-·•*]+([a-zA-Z0-9])", r"\1\2", result)
        if suspicious2 != result:
            found = True
            result = suspicious2
        if found:
            self.detected_types.append("拼接绕过")
        return result

    def _remove_invisible_chars(self, text: str) -> str:
        invisible = ["\u200b", "\u200c", "\u200d", "\ufeff", "\u2060", "\u180e"]
        result = text
        found = False
        for ch in invisible:
            if ch in result:
                found = True
                result = result.replace(ch, "")
        if found:
            self.detected_types.append("零宽字符隐藏")
        return result

    def detect_adversarial_features(self, text: str) -> bool:
        checks = [
            lambda t: bool(
                re.search(
                    r"(?<![a-zA-Z])(zf|zg|zw|tw|td|mg|rb|hg|hk|sq|hs|sb|cnm|nm|djb|nt|zz|wq|fg)(?![a-zA-Z])",
                    t,
                    re.I,
                )
            ),
            lambda t: any(c in t for c in ["\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"]),
            lambda t: bool(re.search(r"[\u4e00-\u9fff][\-·•*\s]{1,}[\u4e00-\u9fff]", t)),
            lambda t: bool(re.search(r"[氵讠钅饣纟礻][\u4e00-\u9fff]", t)),
            lambda t: bool(re.search(r"[＠＃＄％＆（）［］｛｝]", t)),
            lambda t: bool(re.search(r"[a-z]{1,4}[\s\-·•*]+[a-z]{1,4}", t, re.I)),
            lambda t: bool(re.search(r"(?:[\u4e00-\u9fff]|[a-zA-Z0-9])(?:[\s·•*\-_/\\|]){2,}(?:[\u4e00-\u9fff]|[a-zA-Z0-9])", t)),
            lambda t: bool(re.search(r"[一二三四五六七八九零〇０①②③④⑤⑥⑦⑧⑨⑩⒈⒉⒊⒋⒌⒍⒎⒏⒐]{2,}", t)),
            lambda t: any(phrase in t for phrase in PHRASE_HOMOPHONE_MAP.keys()),
        ]
        return any(c(text) for c in checks)


def is_trivial_short_plain(text: str) -> bool:
    t = (text or "").strip()
    # 仅当文本短、且完全是“纯中文/常规标点”时，才视为可跳过的平直短文本；
    # 含拉丁字母/数字的短文本（如 tw、zg）不能被当作 trivial。
    return bool(re.fullmatch(r"[\u4e00-\u9fff\s，。！？,.!?]{1,20}", t))


def adversarial_should_participate(restorer: VariantRestorer, text: str) -> bool:
    if is_trivial_short_plain(text):
        return False
    return restorer.detect_adversarial_features(text)
