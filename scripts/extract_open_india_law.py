#!/usr/bin/env python3
"""Extract a focused English legal PoC dataset (Legislation + Judgments + SQLite FTS5) from Open India Law v2026.08.1."""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import re
import sqlite3
import ssl
import time
import urllib.request
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

MIRROR_BASE = "https://oss-data-in.vaquill.ai/v2026.08.1"
INDEX_URL = "https://oss-data-in.vaquill.ai/index.json"
CONSTITUTION_API_URL = "https://api.github.com/repos/civictech-India/constitution-of-india/contents/constitution_of_india.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) OpenIndiaLawExtractor/1.0"

# Target Central Acts in in_central_legislation.parquet (act_id -> domain tag)
TARGET_CENTRAL_ACTS = {
    "IND_central_2189": "ni_act_138",       # The Negotiable Instruments Act, 1881
    "IND_central_2082": "ni_act_138",       # The Payment and Settlement Systems Act, 2007
    "IND_central_20099": "ni_act_138",      # The Bharatiya Nagarik Suraksha Sanhita, 2023
    "IND_central_2187": "contract_breach",  # The Indian Contract Act, 1872
    "IND_central_1583": "contract_breach",  # The Specific Relief Act, 1963
    "IND_central_1978": "contract_breach",  # The Arbitration and Conciliation Act, 1996
    "IND_central_1565": "both",             # The Limitation Act, 1963
    "IND_central_2191": "both",             # The Code of Civil Procedure, 1908
    "IND_central_20063": "both",            # The Bharatiya Sakshya Adhiniyam, 2023
    "IND_REP_971_1872": "both",             # The Indian Evidence Act, 1872
}

LEGISLATION_FILES = (
    "in_central_legislation.parquet",
    "in_delhi_legislation.parquet",
    "in_maharashtra_legislation.parquet",
    "in_rbi_regulations.parquet",
)

COURT_FILES = {
    "supreme_court": ("in_supreme-court_judgments.parquet", 3_761_559_020),
    "delhi": ("in_delhi_judgments.parquet", 1_988_058_409),
    "bombay": ("in_bombay_judgments.parquet", 4_341_270_597),
}

DEFAULT_COURT_META = {
    "supreme_court": ("Supreme Court of India", "supreme_court", "SCI"),
    "delhi": ("Delhi High Court", "high_court", "DLHC"),
    "bombay": ("Bombay High Court", "high_court", "HCBM"),
}

BOLD_SECTION_RE = re.compile(r"\*\*(\d+[A-Z]?)\.\s*([A-Z\"\[][^\n*]{3,120})")
FOOTNOTE_HEADER_RE = re.compile(r"\b(?:See\s+ss?\.|Subs\.\s+by\s+Act|Ins\.\s+by\s+Act|Added\s+by\s+Act|As\s+to\s+suits)\b", re.I)

# Columns to read from judgment Parquet files (deliberately excluding duplicate text_original to save 4.8 GB of transfer)
JUDGMENT_READ_COLUMNS = [
    "case_id",
    "chunk_id",
    "chunk_index",
    "total_chunks",
    "text",
    "char_start",
    "char_end",
    "page_start",
    "page_end",
    "section_type",
    "section_priority",
    "box_aware",
    "court",
    "court_code",
    "court_type",
    "bench",
    "bench_strength",
    "judges",
    "title",
    "description",
    "petitioner",
    "respondent",
    "disposition",
    "case_number",
    "citation",
    "decision_date",
    "date_of_registration",
    "year",
    "source_url",
    "language_code",
]

NI_STRONG_RE = re.compile(
    r"(?:section|sec\.?|s\.)\s*(?:138|139|141|142|143a|148)\b.{0,120}negotiable\s+instruments"
    r"|negotiable\s+instruments\s+act.{0,120}(?:section|sec\.?|s\.)\s*(?:138|139|141|142|143a|148)\b"
    r"|dishonour\s+of\s+cheque|cheque\s+bounce|statutory\s+demand\s+notice.{0,80}cheque"
    r"|legally\s+enforceable\s+debt\s+or\s+other\s+liability",
    re.IGNORECASE | re.DOTALL,
)
NI_ANCHOR_RE = re.compile(
    r"\b(?:138|139|141|142|143a|148)\b|\bcheque\b|\bdraa?wee\b|\bdishonour",
    re.IGNORECASE,
)
CONTRACT_STRONG_RE = re.compile(
    r"(?:section|sec\.?|s\.)\s*(?:37|39|55|56|62|63|64|65|73|74|75)\b.{0,120}contract\s+act"
    r"|indian\s+contract\s+act.{0,120}(?:section|sec\.?|s\.)\s*(?:37|39|55|56|62|63|64|65|73|74|75)\b"
    r"|breach\s+of\s+contract.{0,200}(?:damages|liquidated|repudiat|specific\s+performance|section\s+7[34])"
    r"|liquidated\s+damages.{0,120}(?:section\s+74|penalty|breach)",
    re.IGNORECASE | re.DOTALL,
)
RBI_RE = re.compile(
    r"dishonour\s+of\s+cheque|cheque\s+truncation|negotiable\s+instruments\s+act|clearing\s+house"
    r"|electronic\s+clearing\s+service|national\s+automated\s+clearing|payment\s+and\s+settlement"
    r"|return\s+of\s+cheques|cheque\s+collection",
    re.IGNORECASE,
)
STATE_ACT_RE = re.compile(
    r"criminal\s+procedure|civil\s+procedure|contract|limitation|court[- ]fees|stamp|commercial\s+courts|arbitration",
    re.IGNORECASE,
)

# Regex patterns to extract case-to-case and case-to-statute citations for the local citation graph
CASE_CITATION_PATTERNS = (
    ("SCC", re.compile(r"\(\d{4}\)\s+\d+\s+SCC\s+(?:\(Cri\)\s+|(?:\(Civ\)\s+)?)?\d+")),
    ("AIR", re.compile(r"\bAIR\s+\d{4}\s+(?:SC|Del|Bom|Mad|Cal|All|Ker|Kar|Pat|P&H|Guj|Raj|AP|Ori)\s+\d+")),
    ("SCR", re.compile(r"\[\d{4}\]\s+(?:Supp\.?\s+)?\d*\s*S\.?C\.?R\.?\s+\d+")),
    ("INSC", re.compile(r"\b\d{4}\s+INSC\s+\d+\b")),
    ("NEUTRAL_HC", re.compile(r"\b\d{4}:(?:DHC|BHC(?:-AS|-OS|-AUG|-NAG|-GOA)?):\d+(?:-[A-Z]+)?\b")),
)
STATUTE_CITATION_RE = re.compile(
    r"\b(?:Section|Sec\.|Article)\s+\d+[A-Z]?(?:\(\d+\))?(?:\s+of\s+the\s+[A-Z][A-Za-z\s]{3,45}?Act(?:,\s*\d{4})?)?",
)


def _ssl_context() -> ssl.SSLContext:
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


SSL_CTX = _ssl_context()


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 90, retries: int = 4) -> bytes:
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=merged)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_err = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed for {url}: {last_err}") from last_err


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class SparseBufferFile(io.RawIOBase):
    """In-memory sparse file wrapper allowing PyArrow to read only fetched byte segments."""

    def __init__(self, size: int, segments: list[tuple[int, bytes]]):
        self.size = size
        self.segments = sorted(segments, key=lambda item: item[0])
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        return self.pos

    def tell(self) -> int:
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        for start, buf in self.segments:
            end = start + len(buf)
            if start <= self.pos < end:
                rel = self.pos - start
                chunk = buf[rel:] if n < 0 else buf[rel : rel + n]
                self.pos += len(chunk)
                return chunk
        raise RuntimeError(f"Unbuffered Parquet read at offset={self.pos} length={n}")


def column_byte_span(rg_meta, col_indices: list[int]) -> tuple[int, int]:
    starts, ends = [], []
    for idx in col_indices:
        col = rg_meta.column(idx)
        start = col.dictionary_page_offset if col.has_dictionary_page and col.dictionary_page_offset else col.data_page_offset
        starts.append(start)
        ends.append(start + col.total_compressed_size)
    return min(starts), max(ends)


def fetch_range_segment(url: str, start: int, end: int) -> tuple[int, bytes]:
    data = http_get(url, headers={"Range": f"bytes={start}-{end - 1}"}, timeout=120)
    return start, data


def download_and_verify_legislation(raw_dir: Path) -> dict[str, dict]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    sums_payload = json.loads(http_get(f"{MIRROR_BASE}/SHA256SUMS.json"))
    expected_files = sums_payload.get("files", {})
    verified = {}
    for filename in LEGISLATION_FILES:
        expected = expected_files.get(filename)
        if not expected:
            raise RuntimeError(f"Missing checksum entry for {filename} in SHA256SUMS.json")
        dest = raw_dir / filename
        if not dest.exists() or dest.stat().st_size != expected["bytes"]:
            data = http_get(f"{MIRROR_BASE}/{filename}", timeout=180)
            dest.write_bytes(data)
        actual_sha = sha256_file(dest)
        if actual_sha != expected["sha256"]:
            raise RuntimeError(f"Checksum mismatch for {filename}: expected {expected['sha256']}, got {actual_sha}")
        verified[filename] = {"bytes": dest.stat().st_size, "sha256": actual_sha}
    return verified


def fetch_constitution_rows(raw_dir: Path) -> list[dict]:
    cache_path = raw_dir / "constitution_of_india.json"
    if not cache_path.exists():
        raw_bytes = http_get(
            CONSTITUTION_API_URL,
            headers={"Accept": "application/vnd.github.v3.raw"},
            timeout=60,
        )
        cache_path.write_bytes(raw_bytes)
    articles = json.loads(cache_path.read_text(encoding="utf-8"))
    rows = []
    for idx, item in enumerate(articles):
        art_num = str(item.get("article", idx))
        sec_title = (item.get("title") or f"Article {art_num}").strip()
        body = (item.get("description") or "").strip()
        if not body:
            continue
        text_lower = body.lower()
        rows.append({
            "act_id": "IND_constitution_1950",
            "chunk_id": f"IND_constitution_1950_art_{art_num}_{idx:03d}",
            "title": "The Constitution of India, 1950",
            "chapter": "Preamble" if art_num == "0" else "Articles",
            "section_number": "Preamble" if art_num == "0" else f"Article {art_num}",
            "section_title": sec_title,
            "section_type": "preamble" if art_num == "0" else "article",
            "text": f"The Constitution of India, 1950 - {'Preamble' if art_num == '0' else 'Article ' + art_num}: {sec_title}\n\n{body}",
            "jurisdiction": "central",
            "state": "central",
            "act_status": "in_force",
            "in_force": True,
            "doc_type": "constitution",
            "instrument_type": "constitution",
            "provision_type": "constitutional_article",
            "legal_subject": "constitutional_law",
            "has_proviso": "provided that" in text_lower or "provided further" in text_lower,
            "has_non_obstante": "notwithstanding anything" in text_lower,
            "delegation_type": None,
            "department": "Legislative Department, Ministry of Law and Justice",
            "regulatory_body": None,
            "acts_referenced": [],
            "defined_terms": [],
            "amendment_count": 0,
            "year": 1950,
            "language_code": "en",
            "source_publisher": "Legislative Department, Ministry of Law and Justice (India Code / CivicTech India)",
            "source_url": "https://legislative.gov.in/constitution-of-india/",
            "mirror_url": CONSTITUTION_API_URL,
            "domain": "constitution",
        })
    return rows


def repair_legislation_row(row: dict) -> dict:
    """Fix footnote-mislabelled section_number values in Vaquill's India Code parser output."""
    text = row.get("text") or ""
    cid = row.get("chunk_id") or ""
    if cid == "IND_central_2187_s001_d4" or (
        cid.startswith("IND_central_2187_s002_p") and "OF THE CONSEQUENCES OF BREACH OF CONTRACT" in text
    ):
        row["section_number"] = "73"
        row["section_title"] = "Compensation for loss or damage caused by breach of contract"
        return row
    sec_num = str(row.get("section_number") or "").strip()
    if (not sec_num or sec_num in {"1", "2", "3"}) and FOOTNOTE_HEADER_RE.search(text[:320]):
        match = BOLD_SECTION_RE.search(text)
        if match:
            row["section_number"] = match.group(1)
            row["section_title"] = match.group(2).strip(" .—-*_")
    return row


def extract_legislation_slice(raw_dir: Path, out_dir: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    counts_by_act: Counter = Counter()

    # 1. Central Legislation
    central_tbl = pq.read_table(raw_dir / "in_central_legislation.parquet")
    for row in central_tbl.to_pylist():
        if (row.get("language_code") or "en") != "en":
            continue
        act_id = row.get("act_id") or ""
        if act_id in TARGET_CENTRAL_ACTS:
            row = repair_legislation_row(row)
            row["domain"] = TARGET_CENTRAL_ACTS[act_id]
            rows.append(row)
            counts_by_act[row.get("title") or act_id] += 1

    # 2. Constitution of India (465 articles normalized to LEGISLATION_SCHEMA + domain)
    const_rows = fetch_constitution_rows(raw_dir)
    rows.extend(const_rows)
    counts_by_act["The Constitution of India, 1950"] += len(const_rows)

    # 3. RBI Regulations on Cheque Dishonour, Clearing & Payment Systems
    rbi_tbl = pq.read_table(raw_dir / "in_rbi_regulations.parquet")
    for row in rbi_tbl.to_pylist():
        if (row.get("language_code") or "en") != "en":
            continue
        blob = f"{row.get('title') or ''} {row.get('section_title') or ''} {row.get('text') or ''}"
        if RBI_RE.search(blob):
            row["domain"] = "ni_act_138"
            rows.append(row)
            counts_by_act["RBI Cheque & Payment Directions"] += 1

    # 4. Delhi & Maharashtra State Legislation relevant to Commercial/Criminal Procedure/Contracts
    for state_file, label in (
        ("in_delhi_legislation.parquet", "Delhi State Commercial/Procedural Acts"),
        ("in_maharashtra_legislation.parquet", "Maharashtra State Commercial/Procedural Acts"),
    ):
        st_tbl = pq.read_table(raw_dir / state_file)
        for row in st_tbl.to_pylist():
            if (row.get("language_code") or "en") != "en":
                continue
            title = row.get("title") or ""
            if STATE_ACT_RE.search(title):
                row["domain"] = "both"
                rows.append(row)
                counts_by_act[label] += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    leg_parquet = out_dir / "target_legislation.parquet"
    leg_csv = out_dir / "target_legislation.csv"
    pq.write_table(pa.Table.from_pylist(rows), leg_parquet, compression="zstd")
    write_csv(rows, leg_csv)
    return rows, dict(counts_by_act)


def classify_case_domain(full_text: str, title: str, description: str) -> str | None:
    header_blob = f"{title}\n{description}\n{full_text}"
    is_ni = bool(NI_STRONG_RE.search(header_blob) and NI_ANCHOR_RE.search(header_blob))
    is_contract = bool(CONTRACT_STRONG_RE.search(header_blob))
    if is_ni and is_contract:
        return "both"
    if is_ni:
        return "ni_act_138"
    if is_contract:
        return "contract_breach"
    return None


def score_case(chunks: list[dict], domain: str) -> tuple[int, int, int, int]:
    first = chunks[0]
    court_rank = 2 if first.get("court_type") == "supreme_court" else 1
    bench = int(first.get("bench_strength") or 1)
    sec_types = {c.get("section_type") for c in chunks}
    has_core_sections = int(bool(sec_types & {"ratio_decidendi", "conclusion", "analysis", "judgment"})) + int(
        bool(sec_types & {"facts", "arguments", "issues"})
    )
    year = int(first.get("year") or 0)
    domain_bonus = 1 if domain in ("ni_act_138", "both") else 0
    return (court_rank, has_core_sections + domain_bonus, bench, year)


def select_row_group_indices(total_rgs: int, limit_rgs: int) -> list[int]:
    if limit_rgs <= 0 or limit_rgs >= total_rgs:
        return list(range(total_rgs))
    if limit_rgs == 1:
        return [0]
    return sorted({round(i * (total_rgs - 1) / (limit_rgs - 1)) for i in range(limit_rgs)})


def scan_court_judgments(
    court_key: str,
    row_group_limit: int,
    max_cases_per_domain: int,
    workers: int = 12,
) -> tuple[list[dict], dict]:
    filename, size = COURT_FILES[court_key]
    url = f"{MIRROR_BASE}/{filename}"
    footer_window = min(size, 2_200_000)
    _, footer_bytes = fetch_range_segment(url, size - footer_window, size)
    pf_meta = pq.ParquetFile(SparseBufferFile(size, [(size - len(footer_bytes), footer_bytes)]))
    schema_names = pf_meta.schema_arrow.names
    col_indices_before = [schema_names.index(c) for c in ("case_id", "chunk_id", "chunk_index", "total_chunks", "text")]
    col_indices_after = [
        schema_names.index(c)
        for c in JUDGMENT_READ_COLUMNS
        if c not in ("case_id", "chunk_id", "chunk_index", "total_chunks", "text")
    ]
    target_rgs = select_row_group_indices(pf_meta.num_row_groups, row_group_limit)

    def fetch_row_group(rg: int) -> tuple[int, list[dict], int]:
        rg_meta = pf_meta.metadata.row_group(rg)
        s1, e1 = column_byte_span(rg_meta, col_indices_before)
        s2, e2 = column_byte_span(rg_meta, col_indices_after)
        seg1 = fetch_range_segment(url, s1, e1)
        seg2 = fetch_range_segment(url, s2, e2)
        sbf = SparseBufferFile(size, [seg1, seg2, (size - len(footer_bytes), footer_bytes)])
        tbl = pq.ParquetFile(sbf).read_row_group(rg, columns=JUDGMENT_READ_COLUMNS)
        en_rows = [r for r in tbl.to_pylist() if r.get("language_code") == "en"]
        return rg, en_rows, (e1 - s1) + (e2 - s2)

    by_case: dict[str, list[dict]] = defaultdict(list)
    bytes_transferred = len(footer_bytes)
    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_row_group, rg) for rg in target_rgs]
        for fut in concurrent.futures.as_completed(futures):
            _, en_rows, rg_bytes = fut.result()
            bytes_transferred += rg_bytes
            for row in en_rows:
                cid = row.get("case_id")
                if cid:
                    by_case[cid].append(row)

    # Keep only complete, ordered cases (0..total_chunks-1) that match our target legal domains
    candidates_by_domain: dict[str, list[tuple[tuple, str, list[dict]]]] = defaultdict(list)
    incomplete_dropped = 0
    for cid, case_chunks in by_case.items():
        dedup_by_idx = {}
        for ch in case_chunks:
            idx = ch.get("chunk_index")
            if idx is not None and idx not in dedup_by_idx:
                dedup_by_idx[int(idx)] = ch
        if not dedup_by_idx:
            continue
        ordered = [dedup_by_idx[i] for i in sorted(dedup_by_idx)]
        expected_total = int(ordered[0].get("total_chunks") or len(ordered))
        if len(ordered) != expected_total or [c["chunk_index"] for c in ordered] != list(range(expected_total)):
            incomplete_dropped += 1
            continue
        full_text = "\n".join(c.get("text") or "" for c in ordered)
        domain = classify_case_domain(full_text, ordered[0].get("title") or "", ordered[0].get("description") or "")
        if not domain:
            continue
        default_court, default_type, default_code = DEFAULT_COURT_META[court_key]
        for c in ordered:
            c["domain"] = domain
            c["court"] = c.get("court") or default_court
            c["court_type"] = c.get("court_type") or default_type
            c["court_code"] = c.get("court_code") or default_code
        rank_key = score_case(ordered, domain)
        bucket = "ni_act_138" if domain in ("ni_act_138", "both") else "contract_breach"
        candidates_by_domain[bucket].append((rank_key, cid, ordered))
        if domain == "both":
            candidates_by_domain["contract_breach"].append((rank_key, cid, ordered))

    selected_cases: dict[str, list[dict]] = {}
    domain_case_counts: Counter = Counter()
    for dom in ("ni_act_138", "contract_breach"):
        ranked = sorted(candidates_by_domain[dom], key=lambda item: item[0], reverse=True)
        kept_for_dom = 0
        for _, cid, ordered in ranked:
            if cid not in selected_cases:
                selected_cases[cid] = ordered
                domain_case_counts[ordered[0]["domain"]] += 1
            kept_for_dom += 1
            if max_cases_per_domain > 0 and kept_for_dom >= max_cases_per_domain:
                break

    emitted_chunks = [ch for cid in sorted(selected_cases) for ch in selected_cases[cid]]
    elapsed = round(time.monotonic() - t0, 2)
    stats = {
        "file": filename,
        "row_groups_scanned": len(target_rgs),
        "total_row_groups": pf_meta.num_row_groups,
        "bytes_transferred": bytes_transferred,
        "english_cases_seen": len(by_case),
        "incomplete_boundary_cases_skipped": incomplete_dropped,
        "cases_selected": len(selected_cases),
        "chunks_selected": len(emitted_chunks),
        "domain_case_counts": dict(domain_case_counts),
        "elapsed_seconds": elapsed,
    }
    return emitted_chunks, stats


def extract_citations_for_cases(chunks: list[dict]) -> list[dict]:
    by_case: dict[str, list[dict]] = defaultdict(list)
    for ch in chunks:
        by_case[ch["case_id"]].append(ch)

    edges: list[dict] = []
    for cid, case_chunks in by_case.items():
        first = case_chunks[0]
        blob = "\n".join(c.get("text") or "" for c in case_chunks)
        seen_targets: set[tuple[str, str]] = set()
        for kind, pattern in CASE_CITATION_PATTERNS:
            for match in pattern.findall(blob):
                norm = re.sub(r"\s+", " ", match.strip())
                if (kind, norm) not in seen_targets:
                    seen_targets.add((kind, norm))
                    edges.append({
                        "source_case_id": cid,
                        "source_court": first.get("court") or "",
                        "source_year": first.get("year"),
                        "target_kind": f"case_{kind.lower()}",
                        "target_ref": norm,
                        "domain": first.get("domain") or "",
                    })
        for match in STATUTE_CITATION_RE.findall(blob):
            norm = re.sub(r"\s+", " ", match.strip())
            if ("statute", norm) not in seen_targets and len(seen_targets) < 60:
                seen_targets.add(("statute", norm))
                edges.append({
                    "source_case_id": cid,
                    "source_court": first.get("court") or "",
                    "source_year": first.get("year"),
                    "target_kind": "statute",
                    "target_ref": norm,
                    "domain": first.get("domain") or "",
                })
    return edges


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = {
                k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                for k, v in row.items()
            }
            writer.writerow(serialized)


def build_sqlite_rag_db(
    db_path: Path,
    legislation_rows: list[dict],
    judgment_chunks: list[dict],
    citation_edges: list[dict],
) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE legislation_provisions (
                chunk_id TEXT PRIMARY KEY,
                act_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                chapter TEXT,
                section_number TEXT,
                section_title TEXT,
                section_type TEXT,
                text TEXT NOT NULL,
                jurisdiction TEXT,
                state TEXT,
                act_status TEXT,
                in_force INTEGER,
                has_proviso INTEGER,
                has_non_obstante INTEGER,
                year INTEGER,
                source_publisher TEXT,
                source_url TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE judgment_cases (
                case_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                court TEXT NOT NULL,
                court_type TEXT NOT NULL,
                court_code TEXT,
                bench TEXT,
                bench_strength INTEGER,
                title TEXT,
                citation TEXT,
                case_number TEXT,
                decision_date TEXT,
                year INTEGER,
                disposition TEXT,
                petitioner TEXT,
                respondent TEXT,
                judges_json TEXT,
                total_chunks INTEGER NOT NULL,
                hierarchy_weight INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE judgment_chunks (
                chunk_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                total_chunks INTEGER NOT NULL,
                domain TEXT NOT NULL,
                court TEXT NOT NULL,
                court_type TEXT NOT NULL,
                bench_strength INTEGER,
                year INTEGER,
                section_type TEXT,
                section_priority INTEGER,
                text TEXT NOT NULL,
                char_start INTEGER,
                char_end INTEGER,
                page_start INTEGER,
                page_end INTEGER,
                FOREIGN KEY(case_id) REFERENCES judgment_cases(case_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE case_citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_case_id TEXT NOT NULL,
                source_court TEXT,
                source_year INTEGER,
                target_kind TEXT NOT NULL,
                target_ref TEXT NOT NULL,
                domain TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE legal_fts USING fts5(
                item_id UNINDEXED,
                case_or_act_id UNINDEXED,
                category UNINDEXED,
                domain UNINDEXED,
                court_or_jurisdiction UNINDEXED,
                section_type UNINDEXED,
                hierarchy_weight UNINDEXED,
                title,
                text
            )
            """
        )

        for r in legislation_rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO legislation_provisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    r.get("chunk_id") or f"{r.get('act_id')}_{r.get('section_number')}",
                    r.get("act_id") or "",
                    r.get("domain") or "both",
                    r.get("title") or "",
                    r.get("chapter"),
                    r.get("section_number"),
                    r.get("section_title"),
                    r.get("section_type"),
                    r.get("text") or "",
                    r.get("jurisdiction"),
                    r.get("state"),
                    r.get("act_status"),
                    int(bool(r.get("in_force"))),
                    int(bool(r.get("has_proviso"))),
                    int(bool(r.get("has_non_obstante"))),
                    r.get("year"),
                    r.get("source_publisher"),
                    r.get("source_url"),
                ),
            )
            conn.execute(
                "INSERT INTO legal_fts VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    r.get("chunk_id") or "",
                    r.get("act_id") or "",
                    "legislation",
                    r.get("domain") or "both",
                    r.get("jurisdiction") or "central",
                    r.get("section_type") or "section",
                    100,
                    f"{r.get('title') or ''} {r.get('section_number') or ''} {r.get('section_title') or ''}",
                    r.get("text") or "",
                ),
            )

        cases_seen = {}
        for ch in judgment_chunks:
            cid = ch["case_id"]
            if cid not in cases_seen:
                is_sc = ch.get("court_type") == "supreme_court"
                bench = int(ch.get("bench_strength") or 1)
                weight = (200 if is_sc else 100) + min(bench, 15) * 5
                cases_seen[cid] = (
                    cid,
                    ch.get("domain") or "",
                    ch.get("court") or "",
                    ch.get("court_type") or "",
                    ch.get("court_code"),
                    ch.get("bench"),
                    bench,
                    ch.get("title"),
                    ch.get("citation"),
                    ch.get("case_number"),
                    ch.get("decision_date"),
                    ch.get("year"),
                    ch.get("disposition"),
                    ch.get("petitioner"),
                    ch.get("respondent"),
                    json.dumps(ch.get("judges") or [], ensure_ascii=False),
                    int(ch.get("total_chunks") or 1),
                    weight,
                )
        conn.executemany(
            "INSERT OR REPLACE INTO judgment_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            list(cases_seen.values()),
        )

        for ch in judgment_chunks:
            cid = ch["case_id"]
            weight = cases_seen[cid][-1] + int(ch.get("section_priority") or 30)
            conn.execute(
                "INSERT OR REPLACE INTO judgment_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ch.get("chunk_id") or f"{cid}_{ch.get('chunk_index', 0):03d}",
                    cid,
                    int(ch.get("chunk_index") or 0),
                    int(ch.get("total_chunks") or 1),
                    ch.get("domain") or "",
                    ch.get("court") or "",
                    ch.get("court_type") or "",
                    int(ch.get("bench_strength") or 1),
                    ch.get("year"),
                    ch.get("section_type") or "body",
                    int(ch.get("section_priority") or 30),
                    ch.get("text") or "",
                    ch.get("char_start"),
                    ch.get("char_end"),
                    ch.get("page_start"),
                    ch.get("page_end"),
                ),
            )
            conn.execute(
                "INSERT INTO legal_fts VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ch.get("chunk_id") or f"{cid}_{ch.get('chunk_index', 0):03d}",
                    cid,
                    "judgment",
                    ch.get("domain") or "",
                    ch.get("court") or "",
                    ch.get("section_type") or "body",
                    weight,
                    f"{ch.get('title') or ''} {ch.get('citation') or ''} {ch.get('case_number') or ''}",
                    ch.get("text") or "",
                ),
            )

        conn.executemany(
            """
            INSERT INTO case_citations (source_case_id, source_court, source_year, target_kind, target_ref, domain)
            VALUES (:source_case_id, :source_court, :source_year, :target_kind, :target_ref, :domain)
            """,
            citation_edges,
        )
        conn.execute("CREATE INDEX idx_judgment_chunks_case ON judgment_chunks(case_id, chunk_index)")
        conn.execute("CREATE INDEX idx_judgment_cases_domain ON judgment_cases(domain, court_type, bench_strength DESC)")
        conn.execute("CREATE INDEX idx_citations_source ON case_citations(source_case_id)")
        conn.execute("CREATE INDEX idx_citations_target ON case_citations(target_ref)")

    return {
        "db_path": str(db_path),
        "db_bytes": db_path.stat().st_size,
        "legislation_provisions": len(legislation_rows),
        "judgment_cases": len(cases_seen),
        "judgment_chunks": len(judgment_chunks),
        "citation_edges": len(citation_edges),
    }


def search_legal_corpus(
    db_path: str | Path,
    query: str,
    domain: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Query the local SQLite FTS5 legal store with BM25 + court/section hierarchy weighting."""
    terms = list(dict.fromkeys(re.findall(r"[A-Za-z0-9]+", query)))[:14]
    if not terms:
        return []
    expression = " OR ".join(f'"{t}"' for t in terms)
    clauses = ["legal_fts MATCH ?"]
    params: list[object] = [expression]
    if domain:
        clauses.append("(domain = ? OR domain = 'both' OR domain = 'constitution')")
        params.append(domain)
    if category:
        clauses.append("category = ?")
        params.append(category)
    params.append(max(1, min(int(limit), 50)))
    sql = f"""
        SELECT item_id, case_or_act_id, category, domain, court_or_jurisdiction,
               section_type, CAST(hierarchy_weight AS INTEGER) AS weight, title,
               substr(text, 1, 700) AS snippet, bm25(legal_fts) AS bm25_score
        FROM legal_fts
        WHERE {' AND '.join(clauses)}
        ORDER BY (bm25(legal_fts) - (CAST(hierarchy_weight AS REAL) * 0.02)) ASC
        LIMIT ?
    """
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data/open_india_law"))
    parser.add_argument("--sc-row-groups", type=int, default=56, help="Row groups to scan for Supreme Court (56 = 100%% of SC)")
    parser.add_argument("--hc-row-groups", type=int, default=6, help="Evenly spaced row groups per High Court (0 = all)")
    parser.add_argument("--max-cases-per-domain", type=int, default=600, help="Max complete cases per court per domain")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--reuse-cached-judgments", action="store_true", help="Reuse existing domain_judgments.parquet if present")
    args = parser.parse_args(argv)

    raw_dir = args.out_dir / "raw"
    print("1. Verifying and downloading legislation & regulatory Parquet files...", flush=True)
    verified_files = download_and_verify_legislation(raw_dir)
    for name, info in verified_files.items():
        print(f"   verified {name}: {info['bytes']/1e6:.2f} MB (sha256={info['sha256'][:12]}...)", flush=True)

    print("2. Extracting statutory, constitutional, and RBI regulatory provisions...", flush=True)
    legislation_rows, act_counts = extract_legislation_slice(raw_dir, args.out_dir)
    for title, count in sorted(act_counts.items(), key=lambda kv: -kv[1]):
        print(f"   {count:5,d} provisions | {title}", flush=True)

    judgments_parquet = args.out_dir / "domain_judgments.parquet"
    judgments_csv = args.out_dir / "domain_judgments.csv"
    manifest_path = args.out_dir / "extraction_manifest.json"
    all_judgment_chunks: list[dict] = []
    court_stats = {}
    if args.reuse_cached_judgments and judgments_parquet.exists():
        print("3. Reusing and normalizing cached domain_judgments.parquet...", flush=True)
        all_judgment_chunks = pq.read_table(judgments_parquet).to_pylist()
        for ch in all_judgment_chunks:
            cid = ch.get("case_id") or ""
            if cid.startswith("DLHC"):
                default_court, default_type, default_code = DEFAULT_COURT_META["delhi"]
            elif cid.startswith("HCBM"):
                default_court, default_type, default_code = DEFAULT_COURT_META["bombay"]
            else:
                default_court, default_type, default_code = DEFAULT_COURT_META["supreme_court"]
            ch["court"] = ch.get("court") or default_court
            ch["court_type"] = ch.get("court_type") or default_type
            ch["court_code"] = ch.get("court_code") or default_code
        if manifest_path.exists():
            court_stats = json.loads(manifest_path.read_text(encoding="utf-8")).get("courts", {})
    else:
        print("3. Extracting complete multi-chunk English judgments (Supreme Court + Delhi HC + Bombay HC)...", flush=True)
        for court_key, rg_limit in (
            ("supreme_court", args.sc_row_groups),
            ("delhi", args.hc_row_groups),
            ("bombay", args.hc_row_groups),
        ):
            print(f"   scanning {court_key} (row_groups={rg_limit})...", flush=True)
            chunks, st = scan_court_judgments(
                court_key=court_key,
                row_group_limit=rg_limit,
                max_cases_per_domain=args.max_cases_per_domain,
                workers=args.workers,
            )
            all_judgment_chunks.extend(chunks)
            court_stats[court_key] = st
            print(
                f"   -> {court_key}: {st['cases_selected']:,} complete cases ({st['chunks_selected']:,} chunks) "
                f"in {st['elapsed_seconds']}s ({st['bytes_transferred']/1e6:.1f} MB transferred)",
                flush=True,
            )

    pq.write_table(pa.Table.from_pylist(all_judgment_chunks), judgments_parquet, compression="zstd")
    write_csv(all_judgment_chunks, judgments_csv)

    print("4. Extracting citation graph edges & building SQLite + FTS5 RAG database...", flush=True)
    citation_edges = extract_citations_for_cases(all_judgment_chunks)
    db_summary = build_sqlite_rag_db(
        args.out_dir / "legal_poc.db",
        legislation_rows=legislation_rows,
        judgment_chunks=all_judgment_chunks,
        citation_edges=citation_edges,
    )

    manifest = {
        "dataset": "open-india-law",
        "version": "v2026.08.1",
        "domains": ["ni_act_138", "contract_breach", "constitution"],
        "verified_legislation_files": verified_files,
        "legislation_counts_by_source": act_counts,
        "courts": court_stats,
        "outputs": {
            "target_legislation_parquet": str(args.out_dir / "target_legislation.parquet"),
            "target_legislation_csv": str(args.out_dir / "target_legislation.csv"),
            "domain_judgments_parquet": str(judgments_parquet),
            "domain_judgments_csv": str(judgments_csv),
            "sqlite_rag_db": db_summary,
        },
    }
    manifest_path = args.out_dir / "extraction_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Done! Manifest written to {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
