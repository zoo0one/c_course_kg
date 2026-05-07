#!/usr/bin/env python3
"""
基于 pycparser 的 C 代码 AST 解析与模式匹配。

功能：
1. 扫描 data/code/*.c 示例代码
2. 识别循环、递归、排序框架、动态内存、输入输出等典型结构
3. 产出代码侧三元组，供后续融合入图谱

用法：
  python -m backend.scripts.extract_code_ast
  python -m backend.scripts.extract_code_ast --input data/code
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

try:
    from pycparser import c_ast, c_parser
except ImportError:  # pragma: no cover - fallback when dependency unavailable
    c_ast = None
    c_parser = None

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT_DIR = ROOT / "data" / "code"
OUT_DIR = ROOT / "data" / "extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "code_ast_triples.jsonl"
REPORT_FILE = OUT_DIR / "code_ast_report.json"

PATTERN_TO_KP = {
    "For": "for语句",
    "While": "while语句",
    "DoWhile": "do-while语句",
    "Switch": "switch语句",
    "Printf": "格式化输入输出",
    "Scanf": "格式化输入输出",
    "Malloc": "动态内存分配",
    "Free": "动态内存分配",
    "Recursion": "递归函数",
    "BubbleSort": "排序算法",
}


def clean_source(text: str) -> str:
    text = re.sub(r"#include\s*<[^>]+>", "", text)
    text = re.sub(r"//.*", "", text)
    return text


if c_ast is not None:
    class PatternVisitor(c_ast.NodeVisitor):
        def __init__(self) -> None:
            self.patterns: Set[str] = set()
            self.function_calls: Dict[str, Set[str]] = {}
            self.current_function: str | None = None
            self.for_count = 0

        def visit_FuncDef(self, node: c_ast.FuncDef) -> None:
            func_name = node.decl.name
            previous = self.current_function
            self.current_function = func_name
            self.function_calls.setdefault(func_name, set())
            self.visit(node.body)
            if func_name in self.function_calls.get(func_name, set()):
                self.patterns.add("Recursion")
            self.current_function = previous

        def visit_For(self, node: c_ast.For) -> None:
            self.patterns.add("For")
            self.for_count += 1
            self.generic_visit(node)

        def visit_While(self, node: c_ast.While) -> None:
            self.patterns.add("While")
            self.generic_visit(node)

        def visit_DoWhile(self, node: c_ast.DoWhile) -> None:
            self.patterns.add("DoWhile")
            self.generic_visit(node)

        def visit_Switch(self, node: c_ast.Switch) -> None:
            self.patterns.add("Switch")
            self.generic_visit(node)

        def visit_FuncCall(self, node: c_ast.FuncCall) -> None:
            if isinstance(node.name, c_ast.ID):
                call_name = node.name.name
                if self.current_function:
                    self.function_calls.setdefault(self.current_function, set()).add(call_name)
                lowered = call_name.lower()
                if lowered == "printf":
                    self.patterns.add("Printf")
                elif lowered == "scanf":
                    self.patterns.add("Scanf")
                elif lowered == "malloc":
                    self.patterns.add("Malloc")
                elif lowered == "free":
                    self.patterns.add("Free")
                elif "sort" in lowered:
                    self.patterns.add("BubbleSort")
            self.generic_visit(node)
else:
    PatternVisitor = None


def detect_patterns_by_text(source: str) -> Set[str]:
    patterns: Set[str] = set()
    lowered = source.lower()
    if re.search(r"\bfor\s*\(", source):
        patterns.add("For")
    if re.search(r"\bwhile\s*\(", source):
        patterns.add("While")
    if re.search(r"\bdo\s*\{", source):
        patterns.add("DoWhile")
    if re.search(r"\bswitch\s*\(", source):
        patterns.add("Switch")
    if "printf(" in lowered:
        patterns.add("Printf")
    if "scanf(" in lowered:
        patterns.add("Scanf")
    if "malloc(" in lowered:
        patterns.add("Malloc")
    if "free(" in lowered:
        patterns.add("Free")
    if re.search(r"int\s+(\w+)\s*\([^\)]*\)\s*\{", source):
        names = re.findall(r"int\s+(\w+)\s*\([^\)]*\)\s*\{", source)
        for name in names:
            if re.search(rf"\b{name}\s*\(", source[source.find(name) + len(name):]):
                patterns.add("Recursion")
                break
    return patterns


def detect_bubble_sort(source: str, for_count: int) -> bool:
    lowered = source.lower()
    if "bubble_sort" in lowered:
        return True
    if for_count >= 2 and "temp" in lowered and "arr[j]" in lowered and "arr[j + 1]" in lowered:
        return True
    return False


def build_triples(file_path: Path, patterns: Set[str], source: str) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    file_id = file_path.stem
    for pattern in sorted(patterns):
        kp_name = PATTERN_TO_KP.get(pattern)
        if not kp_name:
            continue
        triples.append(
            {
                "subject_id": file_id,
                "subject_name": file_path.name,
                "predicate": "IMPLEMENTS_PATTERN",
                "object_id": None,
                "object_name": pattern,
                "mapped_kp": kp_name,
                "evidence": source[:180],
                "source": "code_ast",
                "file_path": str(file_path.relative_to(ROOT)),
            }
        )
    return triples


def parse_file(path: Path) -> List[Dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    cleaned = clean_source(source)
    if c_parser is None or c_ast is None or PatternVisitor is None:
        patterns = detect_patterns_by_text(cleaned)
        for_count = cleaned.count("for (") + cleaned.count("for(")
        if detect_bubble_sort(cleaned, for_count):
            patterns.add("BubbleSort")
        return build_triples(path, patterns, cleaned)

    parser = c_parser.CParser()
    ast = parser.parse(cleaned, filename=path.name)
    visitor = PatternVisitor()
    visitor.visit(ast)
    if detect_bubble_sort(cleaned, visitor.for_count):
        visitor.patterns.add("BubbleSort")
    return build_triples(path, visitor.patterns, cleaned)


def main() -> None:
    parser = argparse.ArgumentParser(description="AST 抽取 C 代码模式")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_DIR), help="输入目录，默认 data/code")
    args = parser.parse_args()

    input_dir = Path(args.input)
    files = sorted(input_dir.glob("*.c"))
    triples: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    for file_path in files:
        try:
            triples.extend(parse_file(file_path))
        except Exception as exc:
            failures.append({"file": str(file_path), "error": str(exc)})

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for triple in triples:
            f.write(json.dumps(triple, ensure_ascii=False) + "\n")

    REPORT_FILE.write_text(
        json.dumps(
            {
                "files_total": len(files),
                "triples_total": len(triples),
                "failures": failures,
                "output": str(OUT_FILE),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Done. files={len(files)} triples={len(triples)} failures={len(failures)}")


if __name__ == "__main__":
    main()
