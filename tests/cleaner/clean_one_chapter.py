#!/usr/bin/env python3
"""单章清洗脚本，通过命令行参数指定章节
用法: venv/bin/python tests/cleaner/clean_one_chapter.py <章节名> <起始页> <结束页>
例:   venv/bin/python tests/cleaner/clean_one_chapter.py ch01_引言 13 28
"""
import sys
import subprocess
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.text_cleaner import clean_text_to_str

TESSERACT = "/opt/homebrew/bin/tesseract"
OUT_DIR = ROOT / "tests" / "cleaner" / "output" / "chapters"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_page_text(pdf_path: str, pg_idx: int) -> str:
    """在子进程中提取单页文本，避免 fitz 卡死影响主进程"""
    script = f"""
import fitz, sys
doc = fitz.open({repr(pdf_path)})
page = doc.load_page({pg_idx})
txt = page.get_text('text') or ''
sys.stdout.write(txt)
doc.close()
"""
    try:
        r = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, timeout=15, text=True, encoding="utf-8", errors="ignore"
        )
        return r.stdout or ""
    except Exception:
        return ""


def ocr_page(pdf_path: str, pg_idx: int, tmpdir: str) -> str:
    txt = extract_page_text(pdf_path, pg_idx)
    if txt.strip():
        return txt
    # 图像 OCR 回退
    try:
        # 用低分辨率(1.2x)减少 tesseract 处理时间，避免卡死
        script = f"""
import fitz, sys
doc = fitz.open({repr(pdf_path)})
page = doc.load_page({pg_idx})
pix = page.get_pixmap(matrix=fitz.Matrix(1.2,1.2), alpha=False)
pix.save({repr(os.path.join(tmpdir, 'p.png'))})
doc.close()
"""
        subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=20)
        png = os.path.join(tmpdir, "p.png")
        if not os.path.exists(png):
            return ""
        out_base = os.path.join(tmpdir, "out")
        subprocess.run(
            [TESSERACT, png, out_base, "-l", "chi_sim+eng", "--psm", "6"],
            capture_output=True, timeout=120,
        )
        out_txt = out_base + ".txt"
        return Path(out_txt).read_text(encoding="utf-8", errors="ignore") if os.path.exists(out_txt) else ""
    except Exception:
        return ""


def main():
    if len(sys.argv) != 4:
        print("Usage: clean_one_chapter.py <name> <start_page> <end_page>")
        sys.exit(1)

    name = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])

    pdf_path = ROOT / "data" / "raw" / "1.pdf"
    # 获取总页数（子进程，避免主进程 fitz 卡死）
    try:
        r = subprocess.run(
            [sys.executable, "-c",
             f"import fitz; doc=fitz.open({repr(str(pdf_path))}); print(doc.page_count); doc.close()"],
            capture_output=True, timeout=15, text=True
        )
        page_count = int(r.stdout.strip())
    except Exception:
        page_count = end  # 回退：直接用 end
    print(f"Processing {name} (pages {start}-{end})...")

    parts = []
    for pg_idx in range(start - 1, min(end, page_count)):
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                txt = ocr_page(str(pdf_path), pg_idx, tmpdir)
            except Exception as e:
                print(f"  p{pg_idx+1}: ERROR {e}", flush=True)
                txt = ""
            parts.append(txt)
            print(f"  p{pg_idx+1}: {len(txt)} chars", flush=True)

    raw = "\n".join(parts)
    cleaned = clean_text_to_str(raw)
    out_path = OUT_DIR / f"{name}.txt"
    out_path.write_text(cleaned, encoding="utf-8")
    print(f"\nSaved: {out_path.name} ({len(cleaned)} chars)")


if __name__ == "__main__":
    main()
