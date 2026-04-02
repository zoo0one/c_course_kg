#!/usr/bin/env python3
"""
批量清洗脚本：从 data/raw/1.pdf 按章节页码范围 OCR + 清洗，
结果保存到 tests/cleaner/output/chapters/ 目录下。
使用 tesseract CLI（subprocess）避免 pytesseract 挂死问题。
运行方式：
    venv/bin/python tests/cleaner/batch_clean_chapters.py
"""

import sys
import subprocess
import tempfile
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import fitz
from backend.services.text_cleaner import clean_text_to_str

PDF_PATH   = ROOT / "data" / "raw" / "1.pdf"
OUT_DIR    = ROOT / "tests" / "cleaner" / "output" / "chapters"
TESSERACT  = "/opt/homebrew/bin/tesseract"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 章节定义：(文件名前缀, 起始页(1-based), 结束页(1-based，含))
# 页码已根据 OCR 实际边界探测校正
CHAPTERS = [
    ("ch01_引言",              13,  28),
    ("ch02_顺序结构",          29,  55),
    ("ch03_分支结构",          56,  78),
    ("ch04_循环结构",          79, 107),
    ("ch05_函数",             108, 132),
    ("ch06_数据类型与表达式",  133, 158),
    ("ch07_数组",             159, 192),
    ("ch08_指针",             193, 226),
    ("ch09_结构",             227, 243),
    ("ch10_函数与程序结构",    244, 271),
    ("ch11_指针进阶",         272, 303),
    ("ch12_文件",             304, 330),
]


def ocr_page_via_cli(page: fitz.Page, tmpdir: str) -> str:
    """将一页渲染为 PNG 并通过 tesseract CLI 识别，返回文本"""
    # 先尝试直接文字层
    txt = page.get_text("text") or ""
    if txt.strip():
        return txt

    # 渲染为 PNG
    png_path = os.path.join(tmpdir, "page.png")
    out_base = os.path.join(tmpdir, "page_out")
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(png_path)

    # 调用 tesseract CLI
    result = subprocess.run(
        [TESSERACT, png_path, out_base, "-l", "chi_sim+eng"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out_txt = out_base + ".txt"
    if os.path.exists(out_txt):
        return Path(out_txt).read_text(encoding="utf-8", errors="ignore")
    return ""


def extract_and_clean(doc: fitz.Document, name: str, start: int, end: int) -> None:
    """提取指定页范围并清洗，写出结果文件"""
    parts = []
    total = min(end, doc.page_count)

    with tempfile.TemporaryDirectory() as tmpdir:
        for page_no in range(start - 1, total):
            page = doc.load_page(page_no)
            txt = ocr_page_via_cli(page, tmpdir)
            if txt.strip():
                parts.append(txt)
            print(f"    p{page_no+1}: {len(txt)} chars", flush=True)

    raw = "\n".join(parts)
    cleaned = clean_text_to_str(raw)
    out_path = OUT_DIR / f"{name}.txt"
    out_path.write_text(cleaned, encoding="utf-8")
    print(f"  => {out_path.name}: {len(cleaned)} chars")


def main():
    print(f"PDF: {PDF_PATH}")
    doc = fitz.open(str(PDF_PATH))
    print(f"{doc.page_count} pages\n")

    for name, start, end in CHAPTERS:
        print(f"\n[{name}] pages {start}-{end}")
        try:
            extract_and_clean(doc, name, start, end)
        except Exception as e:
            print(f"  [ERROR] {e}")

    doc.close()
    print("\nDone:", OUT_DIR)


if __name__ == "__main__":
    main()
