#!/usr/bin/env python3
"""
语料库切分脚本
将每章清洗文本按小节（x.y / x.y.z）切分，输出结构化 JSON 语料库。

输出:
  data/corpus/sections.jsonl   每行一条小节记录
  data/corpus/chapters.json    章节汇总索引

用法:
  venv/bin/python backend/scripts/corpus_builder.py
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
CHAPTER_DIR = ROOT / "tests" / "cleaner" / "output" / "chapters"
OUT_DIR = ROOT / "data" / "corpus"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 章节文件映射（文件名前缀 → chapter_id）
CHAPTER_MAP = [
    ("ch01_引言",              "CH01"),
    ("ch02_顺序结构",          "CH02"),
    ("ch03_分支结构",          "CH03"),
    ("ch04_循环结构",          "CH04"),
    ("ch05_函数",             "CH05"),
    ("ch06_数据类型与表达式",  "CH06"),
    ("ch07_数组",             "CH07"),
    ("ch08_指针",             "CH08"),
    ("ch09_结构",             "CH09"),
    ("ch10_函数与程序结构",    "CH10"),
    ("ch11_指针进阶",         "CH11"),
    ("ch12_文件",             "CH12"),
]

# 小节标题正则：行首 数字.数字 或 数字.数字.数字，后跟空格+标题文字（不超过40字）
# 例："4.1 用格雷戈里公式" "4.1.1 程序解析"
SECTION_RE = re.compile(
    r'^(?P<sec>\d+\.\d+(?:\.\d+)?)'
    r'(?:\s+(?P<title>[^\d][^\n]{0,40}))?$'
)

# 正文引用句排除：如果 title 含以下特征则不作为标题
_NOT_TITLE_HINTS = [
    "节中介绍", "节的", "节例", "节所", "节讨论",
    "节给出", "节中给", "°F", "°C",
]

# 代码块标记
CODE_START = "[CODE_BLOCK_START]"
CODE_END = "[CODE_BLOCK_END]"


def split_into_sections(lines: List[str], chapter_num: int) -> List[Dict[str, Any]]:
    """
    把章节文本按小节标题切分。
    返回列表，每项包含 section_id, title, text, code_blocks。
    """
    sections: List[Dict[str, Any]] = []
    current_sec: Optional[str] = None
    current_title: str = ""
    current_lines: List[str] = []

    def flush():
        if current_sec is None and not current_lines:
            return
        text, code_blocks = extract_text_and_code(current_lines)
        sec_id = current_sec or f"{chapter_num}.0"
        sections.append({
            "section": sec_id,
            "title": current_title or "章节引言",
            "text": text.strip(),
            "code_blocks": code_blocks,
            "line_count": len(current_lines),
            "char_count": len(text),
        })

    for line in lines:
        stripped = line.rstrip("\n")
        m = SECTION_RE.match(stripped)
        if m:
            sec_str = m.group("sec")
            title_str = (m.group("title") or "").strip()
            # 排除正文引用句（如 "4.3 节中介绍的..."）
            if any(hint in title_str for hint in _NOT_TITLE_HINTS):
                current_lines.append(stripped)
                continue
            # 只接受属于本章的小节（首数字 == chapter_num）
            try:
                first_num = int(sec_str.split(".")[0])
            except ValueError:
                first_num = -1
            if first_num == chapter_num:
                flush()
                current_sec = sec_str
                current_title = title_str
                current_lines = []
                continue

        current_lines.append(stripped)

    flush()
    return sections


def extract_text_and_code(lines: List[str]):
    """
    从行列表中分离普通文本和代码块。
    返回 (plain_text, code_blocks_list)。
    """
    plain_parts: List[str] = []
    code_blocks: List[str] = []
    in_code = False
    code_buf: List[str] = []

    for line in lines:
        if line == CODE_START:
            in_code = True
            code_buf = []
            continue
        if line == CODE_END:
            in_code = False
            code_text = "\n".join(code_buf).strip()
            if code_text:
                code_blocks.append(code_text)
            code_buf = []
            continue
        if in_code:
            code_buf.append(line)
        else:
            plain_parts.append(line)

    plain_text = "\n".join(plain_parts)
    return plain_text, code_blocks


def process_chapter(file_prefix: str, chapter_id: str) -> List[Dict[str, Any]]:
    # 找到对应文件
    matches = list(CHAPTER_DIR.glob(f"{file_prefix}.txt"))
    if not matches:
        print(f"  [SKIP] {file_prefix}.txt not found")
        return []
    path = matches[0]
    lines = path.read_text(encoding="utf-8").splitlines()
    chapter_num = int(chapter_id[2:])  # "CH04" → 4

    sections = split_into_sections(lines, chapter_num)
    records = []
    for sec in sections:
        records.append({
            "chapter_id": chapter_id,
            "section": sec["section"],
            "title": sec["title"],
            "text": sec["text"],
            "code_blocks": sec["code_blocks"],
            "char_count": sec["char_count"],
            "code_block_count": len(sec["code_blocks"]),
        })
    print(f"  {chapter_id}: {len(records)} sections, "
          f"{sum(r['char_count'] for r in records)} chars, "
          f"{sum(r['code_block_count'] for r in records)} code blocks")
    return records


def main():
    print("Building corpus...")
    all_records: List[Dict[str, Any]] = []
    chapter_index: List[Dict[str, Any]] = []

    for file_prefix, chapter_id in CHAPTER_MAP:
        records = process_chapter(file_prefix, chapter_id)
        all_records.extend(records)
        chapter_index.append({
            "chapter_id": chapter_id,
            "section_count": len(records),
            "total_chars": sum(r["char_count"] for r in records),
            "total_code_blocks": sum(r["code_block_count"] for r in records),
        })

    # 写出 sections.jsonl
    out_jsonl = OUT_DIR / "sections.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 写出 chapters.json 索引
    out_json = OUT_DIR / "chapters.json"
    out_json.write_text(
        json.dumps(chapter_index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("\nDone.")
    print(f"  sections.jsonl: {len(all_records)} sections")
    print(f"  Total chars: {sum(r['char_count'] for r in all_records)}")
    print(f"  Total code blocks: {sum(r['code_block_count'] for r in all_records)}")
    print(f"  Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
