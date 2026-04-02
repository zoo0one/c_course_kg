#!/usr/bin/env python3
"""
AI 知识点抽取脚本

从语料库 sections.jsonl 中，对每个小节调用 AI 抽取结构化知识点，
与 seed KP 去重合并后输出到 data/extracted/kp_candidates.jsonl。

用法（在系统终端运行，不要在 Cursor IDE 内运行）:
  cd /Users/zuyi/Desktop/毕业设计/c_course_kg
  venv/bin/python backend/scripts/extract_kp.py              # 全量抽取
  venv/bin/python backend/scripts/extract_kp.py --chapter CH04  # 单章测试
  venv/bin/python backend/scripts/extract_kp.py --dry-run       # 只生成 prompt，不调 AI
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests  # type: ignore[reportMissingModuleSource]
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_FILE = ROOT / "data" / "corpus" / "sections.jsonl"
OUT_DIR = ROOT / "data" / "extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "kp_candidates.jsonl"
SEED_SCHEMA = ROOT / "backend" / "scripts" / "course_schema.py"

# ── AI 配置 ──────────────────────────────────────────────
BASE_URL = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))

CATEGORIES = ["syntax", "datatype", "control", "function", "memory", "algorithm", "other"]

# ── Prompt 模板 ───────────────────────────────────────────
SYSTEM_PROMPT = """你是一个 C 语言课程知识图谱构建助手。
你的任务是从教材文本中抽取结构化知识点，输出严格的 JSON 格式。"""

USER_PROMPT_TEMPLATE = """请从以下 C 语言教材的【{section}】小节文本中，抽取 1-4 个核心知识点。

--- 文本开始 ---
{text}
--- 代码示例 ---
{code}
--- 结束 ---

对每个知识点，输出如下 JSON 对象（放入数组中）：
{{
  "name": "知识点名称（简短，如'while循环'）",
  "aliases": "别名，用逗号分隔（如'while语句,当型循环'）",
  "category": "分类，只能是：syntax/datatype/control/function/memory/algorithm/other",
  "summary": "一句话描述（不超过50字）",
  "description": "详细解释，包括概念定义、语法形式、使用场景（100-200字）",
  "code_example": "一个简短的C语言代码示例，展示该知识点用法（如无则填空字符串）",
  "prerequisites": ["前置知识点名称1", "前置知识点名称2"],
  "related": ["相关知识点名称1"]
}}

注意：
- 只输出 JSON 数组，不要任何解释文字
- 如果文本内容太少或无明确知识点，返回空数组 []
- name 要简洁，与 C 语言直接相关
- description 必须基于教材文本内容，不要凭空编造
- code_example 优先从教材代码示例中提取，保持简洁
- prerequisites 填写学习本知识点必须先掌握的其他知识点
"""


def call_ai(section: str, text: str, code_blocks: Optional[List[str]] = None, dry_run: bool = False) -> List[Dict[str, Any]]:
    """调用 AI 抽取知识点，返回知识点列表。"""
    code_str = ""
    if code_blocks:
        code_str = "\n\n".join(code_blocks[:3])[:800]  # 最多3个代码块，限制长度

    prompt = USER_PROMPT_TEMPLATE.format(
        section=section,
        text=text[:1200],  # 限制长度，避免超 token
        code=code_str if code_str else "（无代码示例）"
    )

    if dry_run:
        print(f"    [DRY-RUN] prompt length: {len(prompt)} chars")
        return [{"name": f"[DRY] {section} KP", "aliases": "", "category": "other",
                 "summary": "dry run", "prerequisites": [], "related": []}]

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
        "temperature": 0.3,
        "max_tokens": 800,
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
        # 提取 JSON 数组
        return parse_json_array(content)
    except requests.Timeout:
        print("    [WARN] AI 超时，跳过")
        return []
    except Exception as e:
        print(f"    [WARN] AI 错误: {e}")
        # 尝试打印响应体
        try:
            if response is not None:
                print(f"    [WARN] 响应体: {response.text[:200]}")
        except Exception:
            pass
        return []


def parse_json_array(text: str) -> List[Dict]:
    """从 AI 响应中提取 JSON 数组，容错处理思维链输出。"""
    # DeepSeek-R1 会有 <think>...</think> 标签，先去掉
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.strip()

    # 找最外层的 [ ... ]
    start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1:
        return []
    try:
        arr = json.loads(text[start:end+1])
        if isinstance(arr, list):
            return [item for item in arr if isinstance(item, dict) and 'name' in item]
        return []
    except json.JSONDecodeError:
        return []


def load_seed_kps() -> Dict[str, Dict]:
    """加载 course_schema.py 中的 seed 知识点，用于去重。"""
    seed_kps: Dict[str, Dict] = {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("course_schema", SEED_SCHEMA)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载模块规范: {SEED_SCHEMA}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for kp in mod.KNOWLEDGE_POINTS:
            seed_kps[kp["name"]] = kp
            # 也索引别名
            for alias in kp.get("aliases", "").split(","):
                alias = alias.strip()
                if alias:
                    seed_kps[alias] = kp
    except Exception as e:
        print(f"[WARN] 无法加载 seed KPs: {e}")
    return seed_kps


def is_duplicate(name: str, seed_kps: Dict) -> Optional[str]:
    """检查是否与 seed KP 重复，返回重复的 kp_id 或 None。"""
    if name in seed_kps:
        return seed_kps[name].get("kp_id", "SEED")
    # 简单包含检查
    name_lower = name.lower().replace(" ", "")
    for seed_name, seed_kp in seed_kps.items():
        if name_lower in seed_name.lower().replace(" ", "") or \
           seed_name.lower().replace(" ", "") in name_lower:
            return seed_kp.get("kp_id", "SEED")
    return None


def main():
    parser = argparse.ArgumentParser(description="AI 知识点抽取")
    parser.add_argument("--chapter", help="只处理指定章节，如 CH04")
    parser.add_argument("--dry-run", action="store_true", help="不调用 AI，只测试流程")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="跳过已抽取的小节（断点续传）")
    args = parser.parse_args()

    if not CORPUS_FILE.exists():
        print(f"ERROR: 语料库文件不存在: {CORPUS_FILE}")
        print("请先运行: venv/bin/python backend/scripts/corpus_builder.py")
        sys.exit(1)

    # 加载语料库
    sections = [json.loads(line) for line in CORPUS_FILE.read_text(encoding="utf-8").splitlines()]
    if args.chapter:
        sections = [s for s in sections if s["chapter_id"] == args.chapter.upper()]
        print(f"过滤到 {args.chapter}: {len(sections)} 个小节")

    # 加载 seed KPs
    seed_kps = load_seed_kps()
    print(f"已加载 {len(seed_kps)} 个 seed 知识点索引")

    # 加载已有抽取结果（断点续传）
    done_sections = set()
    existing_records = []
    if args.skip_existing and OUT_FILE.exists():
        for line in OUT_FILE.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done_sections.add(rec.get("_section_key", ""))
            existing_records.append(rec)
        print(f"已有 {len(done_sections)} 个小节的抽取结果，跳过")

    # 写出模式：追加
    out_f = OUT_FILE.open("a", encoding="utf-8") if existing_records else OUT_FILE.open("w", encoding="utf-8")

    total_new = 0
    total_dup = 0

    for sec in sections:
        section_key = f"{sec['chapter_id']}_{sec['section']}"
        if section_key in done_sections:
            continue

        text = sec.get("text", "").strip()
        if len(text) < 50:  # 跳过内容太少的小节
            print(f"  SKIP {section_key} (text too short: {len(text)} chars)")
            continue

        print(f"  Processing {section_key}: {sec['title'][:30]}...", end=" ", flush=True)

        kps = call_ai(sec["section"], text, code_blocks=sec.get("code_blocks", []), dry_run=args.dry_run)
        print(f"→ {len(kps)} KPs")

        for kp in kps:
            dup_id = is_duplicate(kp["name"], seed_kps)
            rec = {
                "_section_key": section_key,
                "chapter_id": sec["chapter_id"],
                "section": sec["section"],
                "section_title": sec["title"],
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
                "duplicate_of": dup_id,  # None 表示新知识点
            }
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()
            if dup_id:
                total_dup += 1
            else:
                total_new += 1

        # 避免请求过快
        if not args.dry_run:
            time.sleep(0.5)

    out_f.close()

    print("\n完成！")
    print(f"  新知识点: {total_new}")
    print(f"  与 seed 重复: {total_dup}")
    print(f"  输出文件: {OUT_FILE}")


if __name__ == "__main__":
    main()
