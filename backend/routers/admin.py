"""管理员相关路由"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel
from pathlib import Path
import csv
import json
import io
import datetime
import uuid
import re
import threading
import time
import os

from dotenv import load_dotenv

import fitz
import pytesseract
from PIL import Image

from backend.db.neo4j import neo4j_client
from backend.services.ai import ai_service
from backend.services.text_cleaner import clean_pdf_text

admin_router = APIRouter(prefix="/admin", tags=["admin"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)
UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
PDF_UPLOAD_DIR = UPLOAD_ROOT / "pdf"
JOBS_DIR = UPLOAD_ROOT / "jobs"
PDF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)
MAX_EXTRACT_RETRIES = 3
MAX_EXTRACT_TEXT_CHARS = 20000
MAX_SCAN_PAGES = int(os.getenv("MAX_SCAN_PAGES", "40"))
EXTRACT_CHAPTER_MODE = os.getenv("EXTRACT_CHAPTER_MODE", "off").strip().lower() == "on"
EXTRACT_PAGE_START = int(os.getenv("EXTRACT_PAGE_START", "1"))
EXTRACT_PAGE_END = int(os.getenv("EXTRACT_PAGE_END", "5"))


def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _job_status_path(job_id: str) -> Path:
    return _job_dir(job_id) / "status.json"


def _read_job_status(job_id: str) -> Dict[str, Any]:
    path = _job_status_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_job_status(job_id: str, status: Dict[str, Any]) -> None:
    path = _job_status_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_json_like(text: str) -> str:
    s = text.strip()
    s = s.replace("```json", "").replace("```", "")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = re.sub(r"/\*[\s\S]*?\*/", "", s)
    s = re.sub(r"//.*", "", s)

    # 为裸 key 自动补双引号：chapters: -> "chapters":
    s = re.sub(
        r'(^|[\{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:',
        lambda m: f'{m.group(1)}"{m.group(2)}":',
        s,
        flags=re.MULTILINE,
    )

    # 将单引号字符串转双引号（容错）
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", lambda m: '"' + m.group(1).replace('"', '\\"') + '"', s)

    # 去掉尾随逗号
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def _load_ai_payload(raw: str) -> Dict[str, Any]:
    candidate_match = re.search(r"\{[\s\S]*\}", raw)
    candidate = candidate_match.group(0).strip() if candidate_match else raw.strip()

    for attempt in [candidate, _normalize_json_like(candidate)]:
        try:
            data = json.loads(attempt)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # 二次修复：让 AI 只做 JSON 纠错，不做内容改写
    repair_prompt = f"""请将下面内容修复为严格 JSON（双引号键名、双引号字符串、无注释、无多余文本）。
只返回 JSON 对象本身：

{candidate}
"""
    repaired = ai_service.generate_text(repair_prompt).strip()
    repaired_match = re.search(r"\{[\s\S]*\}", repaired)
    repaired_candidate = repaired_match.group(0).strip() if repaired_match else repaired.strip()

    for attempt in [repaired_candidate, _normalize_json_like(repaired_candidate)]:
        try:
            data = json.loads(attempt)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    preview = repaired_candidate[:180].replace("\n", " ")
    raise RuntimeError(f"AI 返回 JSON 解析失败，请重试。片段: {preview}")


def _coerce_payload_to_graph_schema(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """将 AI 各种返回结构统一为 chapters/kps/relations 三段式"""

    def _as_list(v: Any) -> List[Any]:
        return v if isinstance(v, list) else []

    chapters = _as_list(payload.get("chapters"))
    kps = _as_list(payload.get("kps"))
    relations = _as_list(payload.get("relations"))

    # 已是标准格式
    if kps or relations:
        return {
            "chapters": chapters if chapters else [],
            "kps": kps,
            "relations": relations,
        }

    # 兼容总结型结构：
    # {
    #   "chapter": "...",
    #   "chapters": [{"chapter_key":"...","keypoints":[...], ...}]
    # }
    normalized_chapters: List[Dict[str, Any]] = []
    normalized_kps: List[Dict[str, Any]] = []
    normalized_relations: List[Dict[str, Any]] = []

    chapter_items = _as_list(payload.get("chapters"))
    root_chapter = payload.get("chapter") if isinstance(payload.get("chapter"), str) else ""

    kp_seq = 1
    chapter_seq = 1

    for ch in chapter_items:
        if not isinstance(ch, dict):
            continue

        # 情况 A: 标准旧结构（chapter_key + keypoints）
        # 情况 B: 两层结构（chapter + chapters:[{chapter_key,keypoints}...]）
        sub_items = _as_list(ch.get("chapters"))
        if sub_items and not _as_list(ch.get("keypoints")):
            parent_title = str(ch.get("chapter") or root_chapter or "").strip()
            for sub in sub_items:
                if not isinstance(sub, dict):
                    continue
                title = str(sub.get("chapter_key") or sub.get("title") or parent_title or f"章节{chapter_seq}").strip()
                chapter_id = f"CH{chapter_seq:02d}"
                normalized_chapters.append({
                    "chapter_id": chapter_id,
                    "title": title,
                    "order": chapter_seq,
                })

                keypoints = _as_list(sub.get("keypoints"))
                kp_ids_in_chapter: List[str] = []

                for kp_name in keypoints:
                    if not isinstance(kp_name, str) or not kp_name.strip():
                        continue
                    kp_id = f"KP{kp_seq:04d}"
                    kp_seq += 1
                    kp_ids_in_chapter.append(kp_id)
                    normalized_kps.append({
                        "kp_id": kp_id,
                        "name": kp_name.strip(),
                        "chapter_id": chapter_id,
                        "section": None,
                        "aliases": "",
                        "source": "pdf_ai",
                    })

                for i in range(len(kp_ids_in_chapter) - 1):
                    normalized_relations.append({
                        "source": kp_ids_in_chapter[i],
                        "target": kp_ids_in_chapter[i + 1],
                        "relation_type": "RELATED",
                        "description": f"同章节知识点关联: {title}",
                    })

                chapter_seq += 1
            continue

        title = str(ch.get("chapter_key") or ch.get("title") or root_chapter or f"章节{chapter_seq}").strip()
        chapter_id = f"CH{chapter_seq:02d}"
        normalized_chapters.append({
            "chapter_id": chapter_id,
            "title": title,
            "order": chapter_seq,
        })

        keypoints = _as_list(ch.get("keypoints"))
        kp_ids_in_chapter: List[str] = []

        for kp_name in keypoints:
            if not isinstance(kp_name, str) or not kp_name.strip():
                continue
            kp_id = f"KP{kp_seq:04d}"
            kp_seq += 1
            kp_ids_in_chapter.append(kp_id)

            normalized_kps.append({
                "kp_id": kp_id,
                "name": kp_name.strip(),
                "chapter_id": chapter_id,
                "section": None,
                "aliases": "",
                "source": "pdf_ai",
            })

        # 章节内相邻知识点建立 RELATED 关系，避免关系全空
        for i in range(len(kp_ids_in_chapter) - 1):
            normalized_relations.append({
                "source": kp_ids_in_chapter[i],
                "target": kp_ids_in_chapter[i + 1],
                "relation_type": "RELATED",
                "description": f"同章节知识点关联: {title}",
            })

        chapter_seq += 1

    return {
        "chapters": normalized_chapters,
        "kps": normalized_kps,
        "relations": normalized_relations,
    }


def _fallback_extract_from_text(text: str) -> Dict[str, List[Dict[str, Any]]]:
    """AI 返回无效结构时的保底抽取（规则法）"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    chapter_titles: List[str] = []
    for ln in lines:
        if re.search(r"第\s*[一二三四五六七八九十0-9]+\s*章", ln):
            chapter_titles.append(ln[:40])
        if len(chapter_titles) >= 6:
            break

    if not chapter_titles:
        chapter_titles = ["C语言基础知识"]

    keyword_re = re.compile(
        r"(变量|数据类型|常量|运算符|表达式|分支|循环|函数|数组|指针|结构体|文件|预处理|编译|调试|递归|字符串|内存|算法|流程图)"
    )
    candidate_kps: List[str] = []
    for ln in lines:
        if len(ln) < 2 or len(ln) > 40:
            continue
        if keyword_re.search(ln):
            candidate_kps.append(ln)
        if len(candidate_kps) >= 30:
            break

    # 去重
    seen = set()
    dedup_kps: List[str] = []
    for name in candidate_kps:
        if name in seen:
            continue
        seen.add(name)
        dedup_kps.append(name)

    chapters: List[Dict[str, Any]] = []
    kps: List[Dict[str, Any]] = []
    relations: List[Dict[str, Any]] = []

    for i, title in enumerate(chapter_titles, start=1):
        chapters.append({"chapter_id": f"CH{i:02d}", "title": title, "order": i})

    if not dedup_kps:
        dedup_kps = ["变量与数据类型", "分支与循环", "函数与数组", "指针与字符串"]

    # 平均分配到章节
    chapter_ids = [c["chapter_id"] for c in chapters] or ["CH01"]
    for i, name in enumerate(dedup_kps[:24], start=1):
        chapter_id = chapter_ids[(i - 1) % len(chapter_ids)]
        kps.append({
            "kp_id": f"KP{i:04d}",
            "name": name,
            "chapter_id": chapter_id,
            "section": None,
            "aliases": "",
            "source": "pdf_fallback",
        })

    for i in range(len(kps) - 1):
        relations.append({
            "source": kps[i]["kp_id"],
            "target": kps[i + 1]["kp_id"],
            "relation_type": "RELATED",
            "description": "基于文本规则抽取的相邻知识点关系",
        })

    return {"chapters": chapters, "kps": kps, "relations": relations}


def _extract_job_runner(job_id: str) -> None:
    try:
        status = _read_job_status(job_id)
        status["status"] = "extracting"
        status["message"] = "正在抽取 PDF 内容..."
        status["updated_at"] = datetime.datetime.now().isoformat()
        _write_job_status(job_id, status)

        pdf_rel = status.get("stored_pdf")
        if not pdf_rel:
            raise RuntimeError("任务缺少 PDF 路径")

        pdf_path = PROJECT_ROOT / pdf_rel
        if not pdf_path.exists():
            raise RuntimeError("PDF 文件不存在")

        job_dir = _job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        scan_dir = job_dir / "scan_pages"
        scan_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        if EXTRACT_CHAPTER_MODE:
            scan_start_page = max(1, min(EXTRACT_PAGE_START, total_pages))
            scan_end_page = max(scan_start_page, min(EXTRACT_PAGE_END, total_pages))
        else:
            scan_start_page = 1
            scan_end_page = min(total_pages, max(1, MAX_SCAN_PAGES))

        text_parts: List[str] = []
        extracted_page_texts: List[Dict[str, Any]] = []
        page_logs: List[Dict[str, Any]] = []
        scanned_page_count = 0

        for i in range(total_pages):
            page_no = i + 1
            if page_no < scan_start_page:
                continue
            if page_no > scan_end_page:
                break

            page = doc.load_page(i)
            scanned_page_count = page_no
            page_text_raw = page.get_text("text")
            page_text = page_text_raw if isinstance(page_text_raw, str) else ""

            if page_text.strip():
                text_parts.append(page_text)
                extracted_page_texts.append({"page": page_no, "text": page_text})
                page_file = scan_dir / f"page_{page_no:03d}.txt"
                page_file.write_text(page_text, encoding="utf-8")
                page_logs.append({
                    "page": page_no,
                    "source": "text",
                    "chars": len(page_text),
                    "file": str(page_file.relative_to(PROJECT_ROOT)),
                    "preview": page_text[:200],
                })
                continue

            # OCR 回退：文本层为空时，渲染图片并识别
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            try:
                ocr_raw = pytesseract.image_to_string(img, lang="chi_sim+eng")
            except Exception:
                ocr_raw = pytesseract.image_to_string(img)
            ocr_text = ocr_raw if isinstance(ocr_raw, str) else ""

            if ocr_text.strip():
                text_parts.append(ocr_text)
                extracted_page_texts.append({"page": page_no, "text": ocr_text})
                page_file = scan_dir / f"page_{page_no:03d}.txt"
                page_file.write_text(ocr_text, encoding="utf-8")
                page_logs.append({
                    "page": page_no,
                    "source": "ocr",
                    "chars": len(ocr_text),
                    "file": str(page_file.relative_to(PROJECT_ROOT)),
                    "preview": ocr_text[:200],
                })
            else:
                page_logs.append({
                    "page": page_no,
                    "source": "empty",
                    "chars": 0,
                    "file": "",
                    "preview": "",
                })
        doc.close()

        full_text = "\n".join(text_parts)
        if not full_text.strip():
            raise RuntimeError("PDF 文本为空（OCR后仍为空），无法抽取")

        # ── 文字清洗管道（10步）──
        status["status"] = "cleaning"
        status["message"] = "正在清洗文字..."
        status["updated_at"] = datetime.datetime.now().isoformat()
        _write_job_status(job_id, status)

        clean_result = clean_pdf_text(full_text)
        (job_dir / "clean_result.json").write_text(
            json.dumps({
                "raw_chars": clean_result.raw_chars,
                "clean_chars": clean_result.clean_chars,
                "chapters_detected": clean_result.chapters_detected,
                "has_code_blocks": clean_result.has_code_blocks,
                "segments_count": len(clean_result.segments),
                "segments": [
                    {
                        "section_id": s.section_id,
                        "title": s.title,
                        "char_count": s.char_count,
                        "has_code": s.has_code,
                        "keywords": s.keywords,
                        "text_preview": s.text[:200],
                    }
                    for s in clean_result.segments
                ],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (job_dir / "clean_text.txt").write_text(clean_result.clean_text, encoding="utf-8")

        # 用清洗后文本替代原始 full_text
        full_text = clean_result.clean_text
        status["clean_summary"] = {
            "raw_chars": clean_result.raw_chars,
            "clean_chars": clean_result.clean_chars,
            "chapters_detected": clean_result.chapters_detected,
            "has_code_blocks": clean_result.has_code_blocks,
            "segments": len(clean_result.segments),
        }
        _write_job_status(job_id, status)

        # 可选：按“章节窗口”固定抽取，便于稳定调试与迭代
        chapter_mode_used = False
        chapter_mode_meta: Dict[str, Any] = {}

        if EXTRACT_CHAPTER_MODE and extracted_page_texts:
            chapter_pages = extracted_page_texts
            chapter_text = "\n".join(p["text"] for p in chapter_pages)
            if chapter_text.strip():
                chapter_mode_used = True
                sampled_text = chapter_text[:MAX_EXTRACT_TEXT_CHARS]
                sample_meta = {
                    "strategy": "fixed_page_range",
                    "full_text_chars": len(full_text),
                    "sampled_chars": len(sampled_text),
                    "page_range": {
                        "start_page": scan_start_page,
                        "end_page": scan_end_page,
                        "matched_pages": len(chapter_pages),
                    },
                }
                chapter_mode_meta = sample_meta["page_range"]

        # 默认：前中后抽样
        if not chapter_mode_used:
            sample_meta: Dict[str, Any] = {}
            if len(full_text) <= MAX_EXTRACT_TEXT_CHARS:
                sampled_text = full_text
                sample_meta = {
                    "strategy": "full",
                    "full_text_chars": len(full_text),
                    "sampled_chars": len(sampled_text),
                }
            else:
                seg = max(2000, MAX_EXTRACT_TEXT_CHARS // 3)
                mid = len(full_text) // 2
                head_start, head_end = 0, seg
                mid_start, mid_end = max(0, mid - seg // 2), min(len(full_text), mid + seg // 2)
                tail_start, tail_end = max(0, len(full_text) - seg), len(full_text)
                sampled_text = (
                    full_text[head_start:head_end]
                    + "\n\n---中段样本---\n\n"
                    + full_text[mid_start:mid_end]
                    + "\n\n---后段样本---\n\n"
                    + full_text[tail_start:tail_end]
                )
                sampled_text = sampled_text[:MAX_EXTRACT_TEXT_CHARS]
                sample_meta = {
                    "strategy": "head_mid_tail",
                    "full_text_chars": len(full_text),
                    "sampled_chars": len(sampled_text),
                    "char_ranges": {
                        "head": [head_start, head_end],
                        "mid": [mid_start, mid_end],
                        "tail": [tail_start, tail_end],
                    },
                }

        prompt = f"""请从以下 C 语言教材文本中抽取知识点，严格返回 JSON（不要 markdown）：

{{
  "chapters": [{{"chapter_id":"CH01","title":"...","order":1}}],
  "kps": [{{"kp_id":"KP0001","name":"...","chapter_id":"CH01","section":"1.1","aliases":"...","source":"pdf_ai"}}],
  "relations": [{{"source":"KP0001","target":"KP0002","relation_type":"PREREQUISITE","description":"..."}}]
}}

规则：
1) chapter_id 格式 CH01..CH99
2) kp_id 格式 KP0001..KP9999
3) relation_type 只能是 PREREQUISITE / RELATED / EXTENDS
4) source 固定为 pdf_ai
5) 只返回 JSON
6) 不允许返回空数组；至少输出 1 个 chapter、8 个 kps、8 个 relations（根据文本尽量抽取）

教材文本（抽样后，最多 {MAX_EXTRACT_TEXT_CHARS} 字）：
{sampled_text}
"""

        (job_dir / "sampled_input.txt").write_text(sampled_text, encoding="utf-8")
        (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (job_dir / "scan_log.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "scanned_pages": scanned_page_count,
                    "total_pdf_pages": total_pages,
                    "scan_start_page": scan_start_page,
                    "scan_end_page": scan_end_page,
                    "scan_limit": scan_end_page - scan_start_page + 1,
                    "max_scan_pages": MAX_SCAN_PAGES,
                    "extracted_pages": len([p for p in page_logs if p.get("chars", 0) > 0]),
                    "empty_pages": len([p for p in page_logs if p.get("source") == "empty"]),
                    "full_text_chars": len(full_text),
                    "sample": sample_meta,
                    "mode": {
                        "page_range_mode": chapter_mode_used,
                        "page_range": chapter_mode_meta,
                    },
                    "pages": page_logs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        if not ai_service.is_ready():
            raise RuntimeError("AI 服务不可用，请先启动 Ollama")

        last_error: Exception | None = None
        payload: Dict[str, Any] | None = None
        chapters: List[Dict[str, Any]] = []
        kps: List[Dict[str, Any]] = []
        relations: List[Dict[str, Any]] = []
        converted_from_legacy = False
        fallback_used = False
        attempt_logs: List[Dict[str, Any]] = []

        job_dir = _job_dir(job_id)
        for attempt in range(1, MAX_EXTRACT_RETRIES + 1):
            try:
                status["status"] = "extracting"
                status["message"] = f"正在抽取 PDF 内容...（第 {attempt}/{MAX_EXTRACT_RETRIES} 次）"
                status["updated_at"] = datetime.datetime.now().isoformat()
                status["retry"] = {"current": attempt, "max": MAX_EXTRACT_RETRIES}
                _write_job_status(job_id, status)

                raw = ai_service.generate_text(prompt)
                raw_file = job_dir / f"raw_attempt_{attempt}.txt"
                raw_file.write_text(raw or "", encoding="utf-8")

                payload = _load_ai_payload(raw)
                normalized = _coerce_payload_to_graph_schema(payload)
                chapters = normalized.get("chapters", [])
                kps = normalized.get("kps", [])
                relations = normalized.get("relations", [])

                legacy_like = isinstance(payload, dict) and isinstance(payload.get("chapters"), list) and not isinstance(payload.get("kps"), list)
                converted_from_legacy = bool(legacy_like and len(kps) > 0)

                (job_dir / "payload_preview.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (job_dir / "normalized_preview.json").write_text(
                    json.dumps(normalized, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                if not isinstance(chapters, list):
                    chapters = []
                if not isinstance(kps, list):
                    kps = []
                if not isinstance(relations, list):
                    relations = []

                attempt_logs.append({
                    "attempt": attempt,
                    "ok": True,
                    "raw_file": str(raw_file.relative_to(PROJECT_ROOT)),
                    "raw_chars": len(raw or ""),
                    "summary": {
                        "chapters": len(chapters),
                        "kps": len(kps),
                        "relations": len(relations),
                    },
                })

                if len(chapters) == 0 and len(kps) == 0 and len(relations) == 0:
                    fallback = _fallback_extract_from_text(sampled_text)
                    chapters = fallback.get("chapters", [])
                    kps = fallback.get("kps", [])
                    relations = fallback.get("relations", [])
                    fallback_used = True
                    (job_dir / "fallback_preview.json").write_text(
                        json.dumps(fallback, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                    # fallback 仍为空，才进入重试
                    if len(chapters) == 0 and len(kps) == 0 and len(relations) == 0:
                        raise RuntimeError("AI 抽取结果为空（chapters/kps/relations 都是 0）")

                    attempt_logs.append({
                        "attempt": attempt,
                        "ok": True,
                        "fallback_used": True,
                        "summary": {
                            "chapters": len(chapters),
                            "kps": len(kps),
                            "relations": len(relations),
                        },
                    })

                break
            except Exception as e:
                last_error = e
                attempt_logs.append({
                    "attempt": attempt,
                    "ok": False,
                    "error": str(e),
                })
                if attempt < MAX_EXTRACT_RETRIES:
                    status["message"] = f"第 {attempt} 次抽取失败，准备重试：{str(e)}"
                    status["updated_at"] = datetime.datetime.now().isoformat()
                    _write_job_status(job_id, status)
                    time.sleep(1.5)
                else:
                    raise RuntimeError(f"连续重试 {MAX_EXTRACT_RETRIES} 次仍失败：{str(e)}")

        if payload is None:
            raise RuntimeError(f"抽取失败：{str(last_error) if last_error else '未知错误'}")

        (job_dir / "chapters.json").write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
        (job_dir / "kps.json").write_text(json.dumps(kps, ensure_ascii=False, indent=2), encoding="utf-8")
        (job_dir / "relations.json").write_text(json.dumps(relations, ensure_ascii=False, indent=2), encoding="utf-8")

        extract_log = {
            "job_id": job_id,
            "scan_log_file": str((job_dir / "scan_log.json").relative_to(PROJECT_ROOT)),
            "sampled_input_file": str((job_dir / "sampled_input.txt").relative_to(PROJECT_ROOT)),
            "prompt_file": str((job_dir / "prompt.txt").relative_to(PROJECT_ROOT)),
            "attempts": attempt_logs,
            "final_summary": {
                "chapters": len(chapters),
                "kps": len(kps),
                "relations": len(relations),
            },
            "transform": {
                "converted_from_legacy_schema": converted_from_legacy,
                "fallback_used": fallback_used,
            },
        }
        (job_dir / "extract_log.json").write_text(json.dumps(extract_log, ensure_ascii=False, indent=2), encoding="utf-8")

        status["status"] = "extracted"
        status["message"] = "抽取完成，可加入审核队列"
        status["updated_at"] = datetime.datetime.now().isoformat()
        status["summary"] = {
            "chapters": len(chapters),
            "kps": len(kps),
            "relations": len(relations),
        }
        status["transform"] = {
            "converted_from_legacy_schema": converted_from_legacy,
            "fallback_used": fallback_used,
        }
        _write_job_status(job_id, status)

    except Exception as e:
        try:
            fail_log = {
                "job_id": job_id,
                "failed": True,
                "error": str(e),
                "failed_at": datetime.datetime.now().isoformat(),
            }
            (_job_dir(job_id) / "extract_log.json").write_text(
                json.dumps(fail_log, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        err_status = {
            "job_id": job_id,
            "status": "failed",
            "message": f"抽取失败: {str(e)}",
            "updated_at": datetime.datetime.now().isoformat(),
        }
        try:
            prev = _read_job_status(job_id)
            err_status.update({k: v for k, v in prev.items() if k not in err_status})
        except Exception:
            pass
        _write_job_status(job_id, err_status)


class KPCreate(BaseModel):
    kp_id: str
    name: str
    chapter_id: str
    section: Optional[str] = None
    aliases: Optional[str] = None
    source: Optional[str] = None


class KPUpdate(BaseModel):
    name: Optional[str] = None
    chapter_id: Optional[str] = None
    section: Optional[str] = None
    aliases: Optional[str] = None
    source: Optional[str] = None


class ApplyReviewedRequest(BaseModel):
    mode: Literal["replace", "append"]


_review_queue: List[Dict[str, Any]] = []
_review_counter = 0


def _add_review(type_: str, action: str, data: dict, source: str = "API") -> dict:
    global _review_counter
    _review_counter += 1
    item = {
        "id": f"REV{_review_counter:03d}",
        "type": type_,
        "action": action,
        "data": data,
        "status": "pending",
        "created_at": datetime.datetime.now().isoformat(),
        "source": source,
    }
    _review_queue.append(item)
    return item


def _apply_review(item: dict) -> None:
    """将审核通过的数据写入 Neo4j"""
    data = item["data"]
    action = item["action"]
    type_ = item["type"]

    if type_ == "chapter":
        if action in ["add", "update"]:
            neo4j_client.run(
                """
                MERGE (c:Chapter {chapter_id: $chapter_id})
                SET c.title = $title, c.order = toInteger($order)
                """,
                {
                    "chapter_id": data.get("chapter_id", ""),
                    "title": data.get("title", ""),
                    "order": data.get("order", 0),
                },
            )
        elif action == "delete":
            neo4j_client.run(
                "MATCH (c:Chapter {chapter_id: $chapter_id}) DETACH DELETE c",
                {"chapter_id": data.get("chapter_id", "")},
            )

    elif type_ == "kp":
        if action == "add":
            neo4j_client.run(
                """
                MERGE (k:KnowledgePoint {kp_id: $kp_id})
                SET k.name = $name, k.chapter_id = $chapter_id,
                    k.section = $section, k.aliases = $aliases, k.source = $source
                """,
                data,
            )
            neo4j_client.run(
                """
                MATCH (c:Chapter {chapter_id: $chapter_id})
                MATCH (k:KnowledgePoint {kp_id: $kp_id})
                MERGE (c)-[:CONTAINS]->(k)
                """,
                data,
            )
        elif action == "update":
            sets = ", ".join(f"k.{k} = ${k}" for k in data if k != "kp_id")
            if sets:
                neo4j_client.run(
                    f"MATCH (k:KnowledgePoint {{kp_id: $kp_id}}) SET {sets}",
                    data,
                )
        elif action == "delete":
            neo4j_client.run(
                "MATCH (k:KnowledgePoint {kp_id: $kp_id}) DETACH DELETE k",
                data,
            )

    elif type_ == "relation" and action == "add":
        rel_type = data.get("relation_type") or data.get("type") or "RELATED"
        neo4j_client.run(
            f"""
            MATCH (a:KnowledgePoint {{kp_id: $source}})
            MATCH (b:KnowledgePoint {{kp_id: $target}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.description = $description
            """,
            {
                "source": data.get("source") or data.get("source_kp_id"),
                "target": data.get("target") or data.get("target_kp_id"),
                "description": data.get("description", ""),
            },
        )


@admin_router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 到 data/uploads/pdf，并创建任务目录"""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    job_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
    safe_name = f"{job_id}_{Path(filename).name}"

    pdf_path = PDF_UPLOAD_DIR / safe_name
    content = await file.read()
    pdf_path.write_bytes(content)

    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "job_id": job_id,
        "status": "uploaded",
        "filename": filename,
        "stored_pdf": str(pdf_path.relative_to(PROJECT_ROOT)),
        "created_at": datetime.datetime.now().isoformat(),
        "message": "PDF 已上传，待执行抽取流程",
    }
    _write_job_status(job_id, status)

    return status


@admin_router.post("/extract/{job_id}/start")
def start_extract(job_id: str):
    status = _read_job_status(job_id)
    if status.get("status") == "extracting":
        return {"ok": True, "job_id": job_id, "status": "extracting", "message": "任务已在执行中"}

    t = threading.Thread(target=_extract_job_runner, args=(job_id,), daemon=True)
    t.start()
    return {"ok": True, "job_id": job_id, "status": "extracting", "message": "已开始抽取"}


@admin_router.get("/extract/{job_id}/status")
def get_extract_status(job_id: str):
    return _read_job_status(job_id)


@admin_router.get("/extract/{job_id}/preview")
def get_extract_preview(job_id: str, limit: int = 20):
    status = _read_job_status(job_id)
    job_dir = _job_dir(job_id)

    def _load(path: Path) -> Any:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    chapters = _load(job_dir / "chapters.json")
    kps = _load(job_dir / "kps.json")
    relations = _load(job_dir / "relations.json")
    raw_payload = _load(job_dir / "payload_preview.json")
    normalized_payload = _load(job_dir / "normalized_preview.json")
    fallback_payload = _load(job_dir / "fallback_preview.json")
    scan_log = _load(job_dir / "scan_log.json")
    extract_log = _load(job_dir / "extract_log.json")

    if not isinstance(chapters, list):
        chapters = []
    if not isinstance(kps, list):
        kps = []
    if not isinstance(relations, list):
        relations = []

    limit = max(1, min(limit, 200))

    return {
        "job_id": job_id,
        "status": status.get("status"),
        "summary": {
            "chapters": len(chapters),
            "kps": len(kps),
            "relations": len(relations),
        },
        "transform": status.get("transform", {}),
        "chapters": chapters[:limit],
        "kps": kps[:limit],
        "relations": relations[:limit],
        "raw_payload": raw_payload,
        "normalized_payload": normalized_payload,
        "fallback_payload": fallback_payload,
        "scan_log": scan_log,
        "extract_log": extract_log,
        "limit": limit,
    }


@admin_router.post("/extract/{job_id}/to-review")
def extract_to_review(job_id: str):
    status = _read_job_status(job_id)
    if status.get("status") != "extracted":
        raise HTTPException(status_code=400, detail="当前任务尚未完成抽取")

    summary = status.get("summary") or {}
    if summary.get("chapters", 0) == 0 and summary.get("kps", 0) == 0 and summary.get("relations", 0) == 0:
        raise HTTPException(status_code=400, detail="抽取结果为空，无法加入审核队列。请重新抽取。")

    job_dir = _job_dir(job_id)
    kps_path = job_dir / "kps.json"
    rels_path = job_dir / "relations.json"
    chapters_path = job_dir / "chapters.json"

    if not kps_path.exists():
        raise HTTPException(status_code=400, detail="缺少抽取结果 kps.json")

    chapters = json.loads(chapters_path.read_text(encoding="utf-8")) if chapters_path.exists() else []
    kps = json.loads(kps_path.read_text(encoding="utf-8"))
    relations = json.loads(rels_path.read_text(encoding="utf-8")) if rels_path.exists() else []

    queued = 0
    for ch in chapters:
        _add_review("chapter", "add", ch, source=f"PDF抽取:{job_id}")
        queued += 1

    for kp in kps:
        existing = neo4j_client.run(
            "MATCH (k:KnowledgePoint {kp_id: $kp_id}) RETURN k",
            {"kp_id": kp.get("kp_id", "")},
        )
        action = "update" if existing else "add"
        _add_review("kp", action, kp, source=f"PDF抽取:{job_id}")
        queued += 1

    for rel in relations:
        _add_review("relation", "add", rel, source=f"PDF抽取:{job_id}")
        queued += 1

    status["status"] = "queued"
    status["message"] = "已加入审核队列"
    status["queued"] = queued
    status["updated_at"] = datetime.datetime.now().isoformat()
    _write_job_status(job_id, status)

    return {"ok": True, "job_id": job_id, "queued": queued}


@admin_router.post("/parse-upload")
async def parse_upload(files: List[UploadFile] = File(...)):
    """解析上传的 CSV/JSON 文件，返回预览数据"""
    chapters = 0
    kps = []
    relations = 0
    relation_rows: List[dict] = []
    errors = []

    for file in files:
        content = await file.read()
        filename = file.filename or ""
        try:
            if filename.endswith(".csv"):
                text = content.decode("utf-8-sig")
                rows = list(csv.DictReader(io.StringIO(text)))
                lower_name = filename.lower()
                if "chapter" in lower_name:
                    chapters += len(rows)
                elif "kp" in lower_name or "knowledge" in lower_name:
                    for row in rows:
                        existing = neo4j_client.run(
                            "MATCH (k:KnowledgePoint {kp_id: $kp_id}) RETURN k",
                            {"kp_id": row.get("kp_id", "")},
                        )
                        kps.append(
                            {
                                "kp_id": row.get("kp_id", ""),
                                "name": row.get("name", ""),
                                "chapter_id": row.get("chapter_id", ""),
                                "section": row.get("section"),
                                "aliases": row.get("aliases"),
                                "source": row.get("source", "文件上传"),
                                "status": "update" if existing else "new",
                            }
                        )
                elif any(k in lower_name for k in ["edge", "relation", "contains"]):
                    relations += len(rows)
                    for row in rows:
                        relation_rows.append(
                            {
                                "source": row.get("source") or row.get("source_kp_id", ""),
                                "target": row.get("target") or row.get("target_kp_id", ""),
                                "relation_type": row.get("relation_type") or row.get("type", "RELATED"),
                                "description": row.get("description", ""),
                            }
                        )
            elif filename.endswith(".json"):
                data = json.loads(content)
                if isinstance(data, list):
                    for item in data:
                        if "kp_id" in item:
                            kps.append({**item, "status": "new"})
                        elif "chapter_id" in item:
                            chapters += 1
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")

    return {
        "chapters": chapters,
        "kps": kps,
        "relations": relations,
        "relation_rows": relation_rows,
        "errors": errors,
    }


@admin_router.post("/confirm-import")
def confirm_import(payload: Dict[str, Any] = Body(...)):
    kps = payload.get("kps", [])
    relations = payload.get("relation_rows", [])

    queued = 0
    for kp in kps:
        action = "update" if kp.get("status") == "update" else "add"
        _add_review("kp", action, kp, source="文件上传")
        queued += 1

    for rel in relations:
        _add_review("relation", "add", rel, source="文件上传")
        queued += 1

    return {"queued": queued, "message": "已加入审核队列"}


@admin_router.get("/review")
def get_review_queue(status: str = "pending"):
    if status == "all":
        return _review_queue
    return [item for item in _review_queue if item["status"] == status]


@admin_router.post("/review/{review_id}/approve")
def approve_review(review_id: str):
    item = next((i for i in _review_queue if i["id"] == review_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item["status"] != "pending":
        raise HTTPException(status_code=400, detail="Item is not pending")
    item["status"] = "approved"
    return {"ok": True, "message": "已批准（待应用）"}


@admin_router.post("/review/batch/approve-all")
def approve_all_reviews():
    count = 0
    for item in _review_queue:
        if item["status"] == "pending":
            item["status"] = "approved"
            count += 1
    return {"ok": True, "approved": count}


@admin_router.post("/review/{review_id}/reject")
def reject_review(review_id: str):
    item = next((i for i in _review_queue if i["id"] == review_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item["status"] = "rejected"
    return {"ok": True}


@admin_router.post("/apply-reviewed")
def apply_reviewed(request: ApplyReviewedRequest):
    approved_items = [i for i in _review_queue if i["status"] == "approved"]
    if not approved_items:
        raise HTTPException(status_code=400, detail="没有已批准的数据可应用")

    if request.mode == "replace":
        neo4j_client.run("MATCH (n) WHERE n:KnowledgePoint OR n:Chapter DETACH DELETE n")

    applied = 0
    failed: List[Dict[str, str]] = []
    for item in approved_items:
        try:
            _apply_review(item)
            applied += 1
        except Exception as e:
            failed.append({"id": item["id"], "error": str(e)})

    stats_rows = neo4j_client.run(
        """
        MATCH (k:KnowledgePoint) WITH COUNT(k) AS total_kps
        MATCH (c:Chapter) WITH total_kps, COUNT(c) AS total_chapters
        MATCH ()-[r]->() WITH total_kps, total_chapters, COUNT(r) AS total_relations
        RETURN {total_kps: total_kps, total_chapters: total_chapters, total_relations: total_relations} AS stats
        """
    )
    stats = stats_rows[0]["stats"] if stats_rows else {"total_kps": 0, "total_chapters": 0, "total_relations": 0}

    return {
        "ok": len(failed) == 0,
        "mode": request.mode,
        "applied": applied,
        "failed": failed,
        "stats": stats,
    }


@admin_router.post("/kps")
def create_kp(kp: KPCreate):
    item = _add_review("kp", "add", kp.model_dump(), source="手动新增")
    return {"ok": True, "review_id": item["id"], "message": "已加入审核队列"}


@admin_router.put("/kps/{kp_id}")
def update_kp(kp_id: str, kp: KPUpdate):
    data = {k: v for k, v in kp.model_dump().items() if v is not None}
    data["kp_id"] = kp_id
    item = _add_review("kp", "update", data, source="手动编辑")
    return {"ok": True, "review_id": item["id"], "message": "已加入审核队列"}


@admin_router.delete("/kps/{kp_id}")
def delete_kp(kp_id: str):
    item = _add_review("kp", "delete", {"kp_id": kp_id}, source="手动删除")
    return {"ok": True, "review_id": item["id"], "message": "已加入审核队列"}
