#!/usr/bin/env python3
"""
文字清洗管道测试脚本
使用已有的扫描结果（sampled_input.txt）验证 10 步清洗效果

用法：
    python tests/cleaner/test_clean.py

清洗通过后可直接删除本目录：
    rm -rf tests/cleaner/
"""
import sys
import json
from pathlib import Path

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.text_cleaner import clean_pdf_text, CleanResult

# ── 输入：已有扫描结果 ──────────────────────────────────────────
JOB_DIR = ROOT / "data/uploads/jobs/20260324201734_ea5c6934"
INPUT_FILE = JOB_DIR / "sampled_input.txt"

# ── 输出：测试结果写到同目录 ────────────────────────────────────
OUT_DIR = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)


def fmt_diff(raw: int, clean: int) -> str:
    pct = (raw - clean) / raw * 100 if raw else 0
    return f"{raw:,} → {clean:,} 字 (减少 {pct:.1f}%)"


def run_test():
    print("=" * 60)
    print("PDF 文字清洗管道测试")
    print("=" * 60)

    if not INPUT_FILE.exists():
        print(f"[ERROR] 输入文件不存在: {INPUT_FILE}")
        sys.exit(1)

    raw_text = INPUT_FILE.read_text(encoding="utf-8")
    print(f"\n[输入] {INPUT_FILE}")
    print(f"  原始字符数: {len(raw_text):,}")
    print(f"  原始行数:   {raw_text.count(chr(10)):,}")

    # 执行清洗
    print("\n[执行] 10 步清洗管道...")
    result: CleanResult = clean_pdf_text(raw_text)

    print("\n[结果] 汇总")
    print(f"  字符量:    {fmt_diff(result.raw_chars, result.clean_chars)}")
    print(f"  检测章节:  {result.chapters_detected} 章")
    print(f"  段落数:    {len(result.segments)} 段")
    print(f"  含代码块:  {'是' if result.has_code_blocks else '否'}")

    print("\n[段落详情]")
    for seg in result.segments:
        kw_str = ", ".join(seg.keywords[:5]) if seg.keywords else "（无）"
        code_tag = " [含代码]" if seg.has_code else ""
        print(f"  [{seg.section_id}] {seg.title[:40]}{code_tag}")
        print(f"    字符数: {seg.char_count}  关键词: {kw_str}")
        # 显示前 120 字预览
        preview = seg.text[:120].replace("\n", "↵")
        print(f"    预览: {preview}")
        print()

    # 对比分析：展示清洗前后典型差异
    print("[清洗前后对比（前 600 字）]")
    print("-" * 40 + " 清洗前 " + "-" * 40)
    print(raw_text[:600])
    print("-" * 40 + " 清洗后 " + "-" * 40)
    print(result.clean_text[:600])
    print("-" * 88)

    # ── 写出文件 ──────────────────────────────────────────────
    out_clean = OUT_DIR / "clean_text.txt"
    out_clean.write_text(result.clean_text, encoding="utf-8")
    print(f"\n[输出] 清洗后文本 → {out_clean}")

    out_json = OUT_DIR / "clean_result.json"
    out_json.write_text(
        json.dumps(
            {
                "raw_chars": result.raw_chars,
                "clean_chars": result.clean_chars,
                "chapters_detected": result.chapters_detected,
                "has_code_blocks": result.has_code_blocks,
                "segments": [
                    {
                        "section_id": s.section_id,
                        "title": s.title,
                        "level": s.level,
                        "char_count": s.char_count,
                        "has_code": s.has_code,
                        "keywords": s.keywords,
                        "text_preview": s.text[:300],
                        "text": s.text,
                    }
                    for s in result.segments
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[输出] 结构化结果 → {out_json}")

    # ── 逐页对比（scan_pages/*.txt）──────────────────────────
    scan_dir = JOB_DIR / "scan_pages"
    if scan_dir.exists():
        page_files = sorted(scan_dir.glob("page_*.txt"))
        print(f"\n[逐页清洗对比] 共 {len(page_files)} 页")
        page_results = []
        for pf in page_files:
            page_raw = pf.read_text(encoding="utf-8")
            page_clean = clean_pdf_text(page_raw)
            page_results.append({
                "file": pf.name,
                "raw_chars": page_clean.raw_chars,
                "clean_chars": page_clean.clean_chars,
                "chapters": page_clean.chapters_detected,
                "segments": len(page_clean.segments),
                "keywords_sample": page_clean.segments[0].keywords[:5] if page_clean.segments else [],
            })
            print(f"  {pf.name}: {fmt_diff(page_clean.raw_chars, page_clean.clean_chars)} | 段={len(page_clean.segments)}")

        out_pages = OUT_DIR / "pages_result.json"
        out_pages.write_text(
            json.dumps(page_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[输出] 逐页结果 → {out_pages}")

    print("\n" + "=" * 60)
    print("测试完成。确认效果满意后执行：")
    print("  rm -rf tests/cleaner/")
    print("=" * 60)


if __name__ == "__main__":
    run_test()
