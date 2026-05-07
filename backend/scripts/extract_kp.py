#!/usr/bin/env python3
"""
AI 知识点抽取脚本

从语料库 sections.jsonl 中，对每个小节调用 AI 抽取结构化知识点，
与 seed KP 去重合并后输出到 data/extracted/kp_candidates.jsonl。

增强点：
- 更强约束 prompt（减少泛化知识点）
- 每节保存原始响应与失败原因（便于定位“为什么没产出”）
- 输出前做基础字段清洗

用法：
  venv/bin/python backend/scripts/extract_kp.py
  venv/bin/python backend/scripts/extract_kp.py --chapter CH04
  venv/bin/python backend/scripts/extract_kp.py --dry-run
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore[reportMissingModuleSource]
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_FILE = ROOT / "data" / "corpus" / "sections.jsonl"
OUT_DIR = ROOT / "data" / "extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "kp_candidates.jsonl"
LOG_DIR = OUT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RAW_RESP_FILE = LOG_DIR / "extract_raw_responses.jsonl"
FAIL_FILE = LOG_DIR / "extract_failures.jsonl"
SEED_SCHEMA = ROOT / "backend" / "scripts" / "course_schema.py"

BASE_URL = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))

CATEGORIES = ["syntax", "datatype", "control", "function", "memory", "algorithm", "other"]
GENERIC_NAMES = {
    "循环结构", "条件判断", "程序解析", "基础概念", "算法优化", "执行流程", "使用场景", "实现要点",
    "函数定义和调用", "项的计算与符号变化", "循环语句的使用场景", "循环结构实现要点",
}
GENERIC_NAME_PATTERNS = [
    r".*的作用$",
    r".*的执行流程$",
    r".*的使用场景$",
    r".*的实现要点$",
    r"^处理.*的方法$",
    r"^条件判断$",
    r"^循环结构$",
    r"^程序解析$",
]
CATEGORY_HINTS = {
    "CH02": ["syntax", "datatype"],
    "CH03": ["control", "syntax", "datatype"],
    "CH04": ["control", "algorithm"],
    "CH05": ["function"],
    "CH06": ["datatype", "syntax"],
    "CH07": ["datatype", "algorithm", "function"],
    "CH08": ["memory", "function", "algorithm"],
    "CH09": ["datatype", "memory", "syntax"],
    "CH10": ["function", "syntax"],
    "CH11": ["memory", "function"],
    "CH12": ["syntax"],
}
RETRY_SUFFIX = "\n\n你上一次输出未通过JSON解析。请严格只输出一个 JSON 数组，最多 2 个对象，不要 ``` 包裹，不要解释文字。"


SYSTEM_PROMPT = """你是一个 C 语言课程知识图谱构建助手。
你必须只输出 JSON 数组，不得输出任何额外文本。
你抽取的必须是“可独立教学、可在图谱中命名”的具体知识点，而不是泛泛描述。
优先抽取：具体语句、具体函数、具体算法、具体数据结构、具体内存机制。
拒绝抽取：章节总结词、作用说明词、实现要点、使用场景、程序解析、处理方法。"""

USER_PROMPT_TEMPLATE = """请从以下 C 语言教材【{section}】小节中抽取知识点。

要求：
1) 只抽取“可入图谱”的具体知识点，不要抽象词或套路词，例如：循环结构、条件判断、程序解析、实现要点、使用场景、处理方法。
2) 每次最多输出 2 个知识点；如果本节没有新的具体知识点，输出 []。
3) 优先输出本章核心粒度的概念，例如：for语句、while语句、break语句、递归函数、动态内存分配、排序算法。
4) 不要把“某题解法”“某程序步骤”“某段代码的作用”当作知识点。
5) 若只是已有 seed 概念的改写，不要重复造新名词。
6) category 只能是: syntax/datatype/control/function/memory/algorithm/other。
7) 本章优先类别：{chapter_categories}
8) prerequisites/related 尽量只使用以下词表中的已有概念；匹配不到可留空：
{allowed_terms}
9) name 必须简洁、标准、可教学，不要用“XX的作用”“XX的执行流程”“使用XX实现YY”这类名字。
10) 输出必须是 JSON 数组，格式严格如下：
[
  {{
    "name": "知识点名称",
    "aliases": "别名1,别名2",
    "category": "control",
    "summary": "一句话描述（<=50字）",
    "description": "基于原文的解释（40-180字）",
    "code_example": "简短C代码示例，没有就空字符串",
    "prerequisites": ["前置1"],
    "related": ["相关1"]
  }}
]

反例（不要输出）：
- 条件判断
- 循环结构
- 处理负数的方法
- break语句的作用
- while语句的执行流程
- 使用while语句实现循环

--- 文本开始 ---
{text}
--- 代码示例 ---
{code}
--- 结束 ---
"""


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_seed_kps() -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    seed_kps: Dict[str, Dict[str, Any]] = {}
    seed_names: List[str] = []
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("course_schema", SEED_SCHEMA)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载模块规范: {SEED_SCHEMA}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for kp in mod.KNOWLEDGE_POINTS:
            name = (kp.get("name") or "").strip()
            if name:
                seed_kps[name] = kp
                seed_names.append(name)
            for alias in (kp.get("aliases") or "").split(","):
                a = alias.strip()
                if a:
                    seed_kps[a] = kp
    except Exception as e:
        print(f"[WARN] 无法加载 seed KPs: {e}")
    return seed_kps, seed_names


def build_allowed_terms(seed_names: List[str], chapter_id: str) -> str:
    base_terms = seed_names[:40]
    return "、".join(base_terms) if base_terms else "(空)"


def chapter_category_hint(chapter_id: str) -> str:
    return "/".join(CATEGORY_HINTS.get(chapter_id, CATEGORIES[:-1]))


def parse_json_array(text: str) -> List[Dict[str, Any]]:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        arr = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []

    if not isinstance(arr, list):
        return []
    return [x for x in arr if isinstance(x, dict)]


def normalize_name(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower()).replace("（", "(").replace("）", ")")


def looks_generic_name(name: str) -> bool:
    name = (name or "").strip()
    if name in GENERIC_NAMES:
        return True
    return any(re.match(p, name) for p in GENERIC_NAME_PATTERNS)


def normalize_aliases(raw: Any) -> str:
    if isinstance(raw, list):
        items = [str(x).strip() for x in raw if str(x).strip()]
    else:
        text = str(raw or "").strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        items = [x.strip(" '\"") for x in text.split(",") if x.strip(" '\"")]
    uniq: List[str] = []
    seen = set()
    for item in items:
        key = normalize_name(item)
        if key and key not in seen:
            seen.add(key)
            uniq.append(item)
    return ",".join(uniq)


def normalize_relation_terms(values: Any, seed_kps: Dict[str, Dict[str, Any]]) -> List[str]:
    if not isinstance(values, list):
        return []
    seen = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or looks_generic_name(text):
            continue
        key = normalize_name(text)
        canonical = seed_kps.get(text, {}).get("name") if text in seed_kps else None
        if not canonical:
            for seed_name, seed in seed_kps.items():
                norm_seed = normalize_name(seed_name)
                if key == norm_seed:
                    canonical = seed.get("name") or seed_name
                    break
        final_text = canonical or text
        final_key = normalize_name(final_text)
        if final_key and final_key not in seen:
            seen.add(final_key)
            result.append(final_text)
    return result


def clean_kp_item(item: Dict[str, Any], chapter_id: str, seed_kps: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    name = str(item.get("name", "")).strip()
    if not name or looks_generic_name(name):
        return None

    category = str(item.get("category", "other")).strip().lower()
    if category not in CATEGORIES:
        category = "other"

    aliases = normalize_aliases(item.get("aliases", ""))
    summary = str(item.get("summary", "")).strip()
    description = str(item.get("description", "")).strip()
    code_example = str(item.get("code_example", "")).strip()

    prerequisites = normalize_relation_terms(item.get("prerequisites", []), seed_kps)
    related = normalize_relation_terms(item.get("related", []), seed_kps)

    if len(description) < 30:
        return None
    if category == "other" and not code_example:
        return None
    chapter_hints = CATEGORY_HINTS.get(chapter_id, [])
    if chapter_hints and category not in chapter_hints and category != "other":
        return None

    return {
        "name": name,
        "aliases": aliases,
        "category": category,
        "summary": summary,
        "description": description,
        "code_example": code_example,
        "prerequisites": prerequisites,
        "related": related,
    }


def is_duplicate(name: str, seed_kps: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if name in seed_kps:
        return seed_kps[name].get("kp_id", "SEED")
    name_lower = name.lower().replace(" ", "")
    for seed_name, seed_kp in seed_kps.items():
        seed_norm = seed_name.lower().replace(" ", "")
        if name_lower in seed_norm or seed_norm in name_lower:
            return seed_kp.get("kp_id", "SEED")
    return None


def call_ai(
    section_key: str,
    section: str,
    chapter_id: str,
    text: str,
    seed_names: List[str],
    seed_kps: Dict[str, Dict[str, Any]],
    code_blocks: Optional[List[str]] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    code_str = ""
    if code_blocks:
        code_str = "\n\n".join(code_blocks[:2])[:600]

    allowed_terms = build_allowed_terms(seed_names, chapter_id)
    prompt = USER_PROMPT_TEMPLATE.format(
        section=section,
        chapter_categories=chapter_category_hint(chapter_id),
        allowed_terms=allowed_terms,
        text=text[:1500],
        code=code_str if code_str else "（无代码示例）",
    )

    if dry_run:
        return [
            {
                "name": f"[DRY]{section}",
                "aliases": "",
                "category": "other",
                "summary": "dry",
                "description": "dry run description for test only",
                "code_example": "",
                "prerequisites": [],
                "related": [],
            }
        ]

    if not BASE_URL or not API_KEY:
        append_jsonl(
            FAIL_FILE,
            {
                "section_key": section_key,
                "reason": "missing_base_url_or_api_key",
                "base_url": bool(BASE_URL),
                "api_key": bool(API_KEY),
            },
        )
        return []

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1100,
    }

    response: Optional[requests.Response] = None
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        append_jsonl(
            RAW_RESP_FILE,
            {
                "section_key": section_key,
                "model": MODEL,
                "raw": content[:8000],
            },
        )

        parsed = parse_json_array(content)
        if not parsed:
            retry_payload = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt + RETRY_SUFFIX},
                ],
                "temperature": 0.0,
                "max_tokens": 800,
            }
            retry_resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=retry_payload,
                timeout=TIMEOUT,
            )
            retry_resp.raise_for_status()
            retry_content = retry_resp.json()["choices"][0]["message"]["content"]
            append_jsonl(
                RAW_RESP_FILE,
                {
                    "section_key": section_key,
                    "model": MODEL,
                    "raw": retry_content[:8000],
                    "retry": True,
                },
            )
            parsed = parse_json_array(retry_content)

        cleaned: List[Dict[str, Any]] = []
        for item in parsed:
            kp = clean_kp_item(item, chapter_id, seed_kps)
            if not kp:
                continue
            if is_duplicate(kp["name"], seed_kps):
                continue
            cleaned.append(kp)

        if not cleaned:
            append_jsonl(
                FAIL_FILE,
                {"section_key": section_key, "reason": "empty_after_parse_or_clean"},
            )

        return cleaned[:2]
    except requests.Timeout:
        append_jsonl(FAIL_FILE, {"section_key": section_key, "reason": "timeout"})
        return []
    except Exception as e:
        detail = ""
        try:
            if response is not None:
                detail = response.text[:500]
        except Exception:
            detail = ""
        append_jsonl(
            FAIL_FILE,
            {
                "section_key": section_key,
                "reason": "request_error",
                "error": str(e),
                "detail": detail,
            },
        )
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 知识点抽取")
    parser.add_argument("--chapter", help="只处理指定章节，如 CH04")
    parser.add_argument("--dry-run", action="store_true", help="不调用 AI，只测试流程")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="跳过已抽取小节")
    args = parser.parse_args()

    if not CORPUS_FILE.exists():
        print(f"ERROR: 语料库文件不存在: {CORPUS_FILE}")
        print("请先运行: venv/bin/python backend/scripts/corpus_builder.py")
        sys.exit(1)

    sections = [json.loads(line) for line in CORPUS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.chapter:
        sections = [s for s in sections if s.get("chapter_id") == args.chapter.upper()]
        print(f"过滤到 {args.chapter}: {len(sections)} 个小节")

    seed_kps, seed_names = load_seed_kps()
    print(f"已加载 {len(seed_kps)} 个 seed 知识点索引")

    done_sections = set()
    has_existing = False
    if args.skip_existing and OUT_FILE.exists():
        for line in OUT_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            done_sections.add(rec.get("_section_key", ""))
        has_existing = bool(done_sections)
        print(f"已有 {len(done_sections)} 个小节抽取结果，启用跳过")

    out_f = OUT_FILE.open("a", encoding="utf-8") if has_existing else OUT_FILE.open("w", encoding="utf-8")

    total_new = 0
    total_dup = 0
    total_empty = 0

    for sec in sections:
        section_key = f"{sec['chapter_id']}_{sec['section']}"
        if section_key in done_sections:
            continue

        text = (sec.get("text") or "").strip()
        if len(text) < 80:
            total_empty += 1
            continue

        print(f"  Processing {section_key}: {sec.get('title', '')[:24]}...", end=" ", flush=True)

        kps = call_ai(
            section_key=section_key,
            section=sec["section"],
            chapter_id=sec["chapter_id"],
            text=text,
            seed_names=seed_names,
            seed_kps=seed_kps,
            code_blocks=sec.get("code_blocks", []),
            dry_run=args.dry_run,
        )
        print(f"→ {len(kps)} KPs")

        if not kps:
            total_empty += 1

        for kp in kps:
            dup_id = is_duplicate(kp["name"], seed_kps)
            rec = {
                "_section_key": section_key,
                "chapter_id": sec["chapter_id"],
                "section": sec["section"],
                "section_title": sec.get("title", ""),
                "name": kp.get("name", ""),
                "aliases": kp.get("aliases", ""),
                "category": kp.get("category", "other"),
                "summary": kp.get("summary", ""),
                "description": kp.get("description", ""),
                "code_example": kp.get("code_example", ""),
                "prerequisites": kp.get("prerequisites", []),
                "related": kp.get("related", []),
                "source": "ai_extracted",
                "reviewed": False,
                "duplicate_of": dup_id,
            }
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()
            if dup_id:
                total_dup += 1
            else:
                total_new += 1

        if not args.dry_run:
            time.sleep(0.5)

    out_f.close()

    print("\n完成！")
    print(f"  新知识点: {total_new}")
    print(f"  与 seed 重复: {total_dup}")
    print(f"  无产出小节: {total_empty}")
    print(f"  输出文件: {OUT_FILE}")
    print(f"  原始响应日志: {RAW_RESP_FILE}")
    print(f"  失败日志: {FAIL_FILE}")


if __name__ == "__main__":
    main()
