#!/usr/bin/env python3
"""Parse and retrieve project-local private evidence without cloud services."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
OUTPUT_DIR = AGENT_DIR / "output" / "knowledge"
CONFIG_FILE = AGENT_DIR / "config.json"
SUPPORTED = {".txt", ".md", ".csv", ".docx", ".xlsx", ".pdf"}
LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
CHINESE_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokens(text: str) -> list[str]:
    result = [item.lower() for item in LATIN_TOKEN_RE.findall(text)]
    for run in CHINESE_RUN_RE.findall(text):
        if len(run) == 1:
            result.append(run)
        else:
            result.extend(run[index:index + 2] for index in range(len(run) - 1))
    return result


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        text = "".join(
            node.text or ""
            for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        ).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def read_xlsx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.itertext())
                for node in root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si")
            ]
        rows = []
        sheets = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        for sheet_name in sheets:
            root = ET.fromstring(archive.read(sheet_name))
            rows.append(f"## {Path(sheet_name).stem}")
            for row in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                values = []
                for cell in row.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    value_node = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    value = value_node.text if value_node is not None and value_node.text is not None else ""
                    if cell.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    elif cell.attrib.get("t") == "inlineStr":
                        inline = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")
                        value = "".join(inline.itertext()) if inline is not None else ""
                    values.append(value)
                if any(values):
                    rows.append("\t".join(values))
        return "\n".join(rows)


def read_pdf(path: Path) -> str:
    if shutil.which("pdftotext"):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "document.txt"
            subprocess.run(["pdftotext", "-layout", str(path), str(target)], check=True, capture_output=True)
            return target.read_text(encoding="utf-8", errors="replace")
    try:
        import fitz  # type: ignore
        with fitz.open(path) as document:
            return "\n\f\n".join(page.get_text() for page in document)
    except ImportError:
        try:
            from pypdf import PdfReader  # type: ignore
            return "\n\f\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        except ImportError as exc:
            if shutil.which("mdls"):
                result = subprocess.run(
                    ["mdls", "-raw", "-name", "kMDItemTextContent", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                extracted = result.stdout.strip()
                if result.returncode == 0 and extracted not in {"", "(null)"}:
                    return extracted
            raise RuntimeError("PDF parser unavailable: macOS text extraction failed; install pdftotext, PyMuPDF or pypdf") from exc


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
            return "\n".join("\t".join(row) for row in csv.reader(handle))
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".pdf":
        return read_pdf(path)
    raise RuntimeError(f"unsupported file type: {suffix}")


def chunks(text: str, max_chars: int = 1800, overlap: int = 180) -> list[dict]:
    pages = text.split("\f")
    result = []
    for page_number, page in enumerate(pages, 1):
        blocks = [item.strip() for item in re.split(r"\n{2,}|(?=^#{1,4}\s)", page, flags=re.M) if item.strip()]
        section = ""
        buffer = ""
        for block in blocks:
            first_line = block.splitlines()[0].strip()
            if first_line.startswith("#") or (len(first_line) <= 80 and not first_line.endswith(("。", ".", "；", ";"))):
                section = first_line.lstrip("# ")
            candidate = f"{buffer}\n{block}".strip()
            if len(candidate) <= max_chars:
                buffer = candidate
                continue
            if buffer:
                result.append({"page": page_number, "section": section, "text": buffer})
            buffer = candidate[-(max_chars + overlap):]
        if buffer:
            result.append({"page": page_number, "section": section, "text": buffer})
    return result


def load_manifests(directories: list[Path]) -> dict[str, dict]:
    result = {}
    for directory in directories:
        path = directory / "manifest.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("documents", []):
            if item.get("file"):
                result[str(item["file"])] = item
    return result


def resolve_knowledge_directories(settings: dict) -> list[Path]:
    values = []
    environment_name = str(settings.get("environment_variable", "INDUSTRY_REPORT_KNOWLEDGE_DIR"))
    environment_value = os.environ.get(environment_name, "").strip()
    if environment_value:
        values.extend(item for item in environment_value.split(os.pathsep) if item)
    elif settings.get("paths"):
        values.extend(str(item) for item in settings["paths"] if str(item).strip())
    elif str(settings.get("directory", "")).strip():
        values.append(str(settings["directory"]))
    else:
        values.append(str(settings.get("default_directory", "~/Documents/Industry Report Knowledge")))

    result = []
    for value in values:
        configured = Path(value).expanduser()
        resolved = configured if configured.is_absolute() else (AGENT_DIR / configured).resolve()
        if resolved not in result:
            result.append(resolved)
    return result


def initialize_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    readme = directory / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Industry Report Knowledge\n\n"
            "把允许 Industry Report Agent 使用的 PDF、Word、Excel、CSV、Markdown 或 TXT 文件拖到这里。\n"
            "资料保留在本机；命中的片段会作为 PRI 私有证据进入当前模型上下文。\n",
            encoding="utf-8",
        )


def bm25(query: list[str], docs: list[list[str]]) -> list[float]:
    if not docs:
        return []
    average_length = sum(map(len, docs)) / len(docs) or 1
    document_frequency = Counter(token for token in set(query) for doc in docs if token in doc)
    scores = []
    for doc in docs:
        frequencies = Counter(doc)
        score = 0.0
        for token in query:
            if not frequencies[token]:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            tf = frequencies[token]
            score += idf * tf * 2.2 / (tf + 1.2 * (1 - 0.75 + 0.75 * len(doc) / average_length))
        scores.append(score)
    return scores


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    settings = config.get("knowledge", {})
    knowledge_directories = resolve_knowledge_directories(settings)
    for directory in knowledge_directories:
        initialize_directory(directory)
    top_k = int(settings.get("top_k_per_question", 6))
    manifest = load_manifests(knowledge_directories)
    ignored_names = {"README.md", "manifest.json", "manifest.example.json"}
    files = sorted({
        path
        for directory in knowledge_directories
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED and path.name not in ignored_names
    })
    documents, all_chunks, errors = [], [], []
    for index, path in enumerate(files, 1):
        metadata = manifest.get(path.name, {})
        if metadata.get("allow_in_analysis", True) is False:
            continue
        document_id = f"DOC-PRI-{index:04d}"
        try:
            text = read_file(path)
            if not text.strip():
                raise RuntimeError("no extractable text")
            document_chunks = chunks(text)
            documents.append({"document_id": document_id, "file_name": path.name, "characters": len(text), "chunks": len(document_chunks), "metadata": metadata})
            for chunk_index, item in enumerate(document_chunks, 1):
                all_chunks.append({**item, "chunk_id": f"{document_id}-C{chunk_index:04d}", "document_id": document_id, "file_name": path.name, "metadata": metadata})
        except Exception as exc:
            errors.append({"file": path.name, "error": str(exc)})

    questions = config.get("research_questions", [])
    doc_tokens = [tokens(item["text"]) for item in all_chunks]
    ledger, seen = [], set()
    for question in questions:
        question_id = str(question.get("id", "")).strip()
        question_text = str(question.get("question") or question.get("text") or question.get("title") or "").strip()
        query_tokens = tokens(" ".join([question_text, config.get("target", {}).get("company", ""), config.get("target", {}).get("industry", "")]))
        scores = bm25(query_tokens, doc_tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        for chunk_index, score in ranked[:top_k]:
            if score <= 0:
                continue
            chunk = all_chunks[chunk_index]
            key = (question_id, chunk["chunk_id"])
            if key in seen:
                continue
            seen.add(key)
            metadata = chunk["metadata"]
            ledger.append({
                "evidence_id": f"PRI-{len(ledger) + 1:04d}",
                "question_ids": [question_id] if question_id else [],
                "document_id": chunk["document_id"],
                "chunk_id": chunk["chunk_id"],
                "file_name": chunk["file_name"],
                "page": chunk["page"],
                "section": chunk["section"],
                "excerpt": chunk["text"][:1200],
                "retrieval_score": round(score, 4),
                "source_type": "user_provided_private",
                "confidentiality": metadata.get("confidentiality", "private"),
                "allow_quote_in_report": metadata.get("allow_quote_in_report", False),
                "allow_public_export": metadata.get("allow_public_export", False),
                "method_note": metadata.get("method_note", "not_provided"),
                "evidence_status": "private_directional_input",
            })

    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "pass" if not errors else "partial",
        "storage": "project_local",
        "knowledge_directories": [str(item) for item in knowledge_directories],
        "cloud_upload": False,
        "files_discovered": len(files),
        "documents_parsed": len(documents),
        "chunks_created": len(all_chunks),
        "private_evidence_items": len(ledger),
        "errors": errors,
        "note": "Private evidence remains separate from the public evidence ledger and cannot satisfy public-source quality gates.",
    }
    (OUTPUT_DIR / "parsed_documents.json").write_text(json.dumps({"documents": documents, "chunks": all_chunks}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "private_evidence_ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "knowledge_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
