"""Indian legal RAG retrieval over data/open_india_law/legal_poc.db (stdlib sqlite3 + FTS5)."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEGAL_DB = ROOT / "data" / "open_india_law" / "legal_poc.db"

DOMAIN_LABELS = {
    "ni_act_138": "Cheque Dishonour & Banking (Section 138 Negotiable Instruments Act, 1881 + RBI Directions)",
    "contract_breach": "Commercial Breach of Contract & Damages (Indian Contract Act, 1872 + Specific Relief Act, 1963)",
    "constitution": "Constitutional Writ, Appellate & Limitation Jurisdiction (Constitution of India, 1950 + Limitation Act, 1963)",
    "both": "Commercial Contract & Cheque Dishonour Dispute (NI Act, 1881 + Indian Contract Act, 1872)",
}

SAMPLE_SCENARIOS = {
    "ni_act_138": (
        "A Bengaluru electronics distributor issued a post-dated cheque for Rs. 35,00,000 marked as a security deposit "
        "under a dealership supply agreement with a Mumbai manufacturer. After a dispute over delayed and defective shipments, "
        "the distributor instructed its bank to stop payment, and the cheque was returned unpaid with memo 'Payment Stopped by Drawer'. "
        "The manufacturer sent a statutory demand notice 28 days after receiving the bank return memo; the distributor replied "
        "claiming the cheque was given purely by way of security and no crystallized debt was due on the date of drawal. "
        "The manufacturer now files a complaint under Section 138 read with Section 141 of the Negotiable Instruments Act, 1881 "
        "against the company and its non-executive directors."
    ),
    "contract_breach": (
        "An infrastructure contractor entered into a fixed-price turnkey supply and installation contract in Delhi with "
        "a stipulated liquidated damages clause of 10% of the contract value for delay under Section 74 of the Indian Contract Act, 1872. "
        "Midway through performance, sudden port restrictions and customs notifications delayed imported components by four months. "
        "The employer terminated the contract for repudiatory breach, forfeited the entire 10% performance bank guarantee without "
        "proving actual loss, and procured replacement equipment at a higher price. The contractor claims frustration and extension "
        "of time under Sections 55 and 56, challenges the forfeiture under Sections 73 and 74, and seeks an injunction."
    ),
    "constitution": (
        "A state procurement authority blacklisted an MSME engineering supplier for three years and invoked its earnest money deposit "
        "without issuing a specific show-cause notice proposing blacklisting or granting a personal hearing. The supplier challenges "
        "the order directly before the High Court under Article 226 of the Constitution of India alleging violation of Article 14 "
        "and natural justice, while the state authority objects that the contract contains an arbitration clause and a civil remedy."
    ),
}

# Core statutory chunk_ids per domain so essential statutory ingredients & loopholes are always included
ANCHOR_CHUNKS = {
    "ni_act_138": [
        "IND_central_2189_s138_p0",
        "IND_central_2189_s138_p1",
        "IND_central_2189_s139",
        "IND_central_2189_s141_p0",
        "IND_central_2189_s142_p0",
        "IND_constitution_1950_art_141_153",
    ],
    "contract_breach": [
        "IND_central_2187_s001_d4",  # Repaired Section 73 main text
        "IND_central_2187_s074_p0",  # Section 74 liquidated damages / penalty
        "IND_central_2187_s055_p0",  # Section 55 time of essence
        "IND_central_2187_s056_p0",  # Section 56 impossibility / frustration
        "IND_central_2187_s039_p0",  # Section 39 refusal to perform promise wholly
        "IND_constitution_1950_art_141_153",
    ],
    "constitution": [
        "IND_constitution_1950_art_14_16",
        "IND_constitution_1950_art_19_22",
        "IND_constitution_1950_art_32_37",
        "IND_constitution_1950_art_136_147",
        "IND_constitution_1950_art_141_153",
        "IND_constitution_1950_art_226_239",
    ],
}

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "under", "into", "after", "before", "were",
    "was", "are", "has", "had", "have", "its", "their", "they", "them", "who", "whom", "which", "what",
    "when", "where", "why", "how", "any", "all", "both", "each", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "than", "too", "very", "can", "will", "just", "should", "now", "case",
}


def detect_legal_domain(text: str, requested: str = "auto") -> str:
    if requested in ("ni_act_138", "contract_breach", "constitution", "both"):
        return requested
    lower = (text or "").lower()
    is_ni = any(
        k in lower
        for k in ("138", "139", "141", "142", "cheque", "dishonour", "negotiable instrument", "drawer", "drawee", "return memo")
    )
    is_con = any(
        k in lower
        for k in (
            "breach", "contract", "liquidated damages", "section 73", "section 74", "section 55", "section 56",
            "frustration", "specific performance", "forfeiture", "bank guarantee", "termination", "repudiat",
        )
    )
    is_const = any(
        k in lower
        for k in ("article 14", "article 19", "article 21", "article 32", "article 136", "article 226", "writ", "fundamental right", "unconstitutional")
    )
    if is_ni and is_con:
        return "both"
    if is_ni:
        return "ni_act_138"
    if is_con:
        return "contract_breach"
    if is_const:
        return "constitution"
    return "ni_act_138"


def ensure_legal_db(db_path: Path = DEFAULT_LEGAL_DB) -> Path:
    """Auto-build legal_poc.db from tracked Parquet slices if a fresh clone does not have the SQLite file yet."""
    path = Path(db_path)
    if path.exists():
        return path
    leg_parquet = path.parent / "target_legislation.parquet"
    jud_parquet = path.parent / "domain_judgments.parquet"
    if leg_parquet.exists() and jud_parquet.exists():
        try:
            import pyarrow.parquet as pq
            from scripts.extract_open_india_law import build_sqlite_rag_db, extract_citations_for_cases
            leg_rows = pq.read_table(leg_parquet).to_pylist()
            jud_rows = pq.read_table(jud_parquet).to_pylist()
            edges = extract_citations_for_cases(jud_rows)
            build_sqlite_rag_db(path, leg_rows, jud_rows, edges)
        except Exception:
            pass
    return path


def legal_status(db_path: Path = DEFAULT_LEGAL_DB) -> dict:
    path = ensure_legal_db(Path(db_path))
    if not path.exists():
        return {"available": False, "domains": list(DOMAIN_LABELS)}
    try:
        with closing(sqlite3.connect(path)) as conn:
            provisions = conn.execute("SELECT COUNT(*) FROM legislation_provisions").fetchone()[0]
            cases = conn.execute("SELECT COUNT(*) FROM judgment_cases").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM judgment_chunks").fetchone()[0]
            citations = conn.execute("SELECT COUNT(*) FROM case_citations").fetchone()[0]
        return {
            "available": True,
            "dataset": "vaquill/open-india-law",
            "version": "v2026.08.1",
            "legislation_provisions": provisions,
            "judgment_cases": cases,
            "judgment_chunks": chunks,
            "citation_edges": citations,
            "domains": list(DOMAIN_LABELS),
        }
    except sqlite3.Error:
        return {"available": False, "domains": list(DOMAIN_LABELS)}


def _fts_expression(query: str) -> str:
    tokens = [
        t for t in dict.fromkeys(re.findall(r"[A-Za-z0-9]+", query or ""))
        if (len(t) >= 3 or t.isdigit()) and t.lower() not in STOPWORDS
    ][:16]
    if not tokens:
        tokens = ["Section", "138", "73", "74", "Contract", "Cheque"]
    return " OR ".join(f'"{t}"' for t in tokens)


def _clean_excerpt(text: str, max_len: int = 440) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len].rsplit(" ", 1)[0]
    return cut + "."


def retrieve_legal_dossier(
    scenario: str,
    domain: str = "auto",
    max_chars: int = 2600,
    db_path: Path = DEFAULT_LEGAL_DB,
) -> dict:
    """Build a citation-grounded Indian legal source dossier for a scenario from legal_poc.db."""
    path = ensure_legal_db(Path(db_path))
    if not path.exists():
        raise FileNotFoundError("Indian legal corpus database (data/open_india_law/legal_poc.db) is not initialized.")

    resolved_domain = detect_legal_domain(scenario, domain)
    effective_scenario = (scenario or "").strip()
    if not effective_scenario:
        sample_key = "ni_act_138" if resolved_domain == "both" else resolved_domain
        effective_scenario = SAMPLE_SCENARIOS.get(sample_key, SAMPLE_SCENARIOS["ni_act_138"])
        resolved_domain = detect_legal_domain(effective_scenario, domain)

    fts_expr = _fts_expression(effective_scenario)
    anchor_ids: list[str] = []
    if resolved_domain == "both":
        anchor_ids = ANCHOR_CHUNKS["ni_act_138"][:3] + ANCHOR_CHUNKS["contract_breach"][:3]
    else:
        anchor_ids = list(ANCHOR_CHUNKS.get(resolved_domain, ANCHOR_CHUNKS["ni_act_138"]))

    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row

        # 1. Fetch statutory anchors + FTS-matched provisions
        statutes_by_id: dict[str, dict] = {}
        if anchor_ids:
            placeholders = ",".join("?" for _ in anchor_ids)
            for row in conn.execute(
                f"SELECT * FROM legislation_provisions WHERE chunk_id IN ({placeholders})",
                anchor_ids,
            ).fetchall():
                statutes_by_id[row["chunk_id"]] = dict(row)

        dom_clause = (
            "AND l.domain IN ('ni_act_138', 'contract_breach', 'both', 'constitution')"
            if resolved_domain == "both"
            else "AND l.domain IN (?, 'both', 'constitution')"
        )
        dom_params = [fts_expr] if resolved_domain == "both" else [fts_expr, resolved_domain]
        fts_statutes = conn.execute(
            f"""
            SELECT l.*
            FROM legal_fts f
            JOIN legislation_provisions l ON l.chunk_id = f.item_id
            WHERE f.legal_fts MATCH ? AND f.category = 'legislation' {dom_clause}
            ORDER BY bm25(f.legal_fts) ASC
            LIMIT 8
            """,
            dom_params,
        ).fetchall()
        for row in fts_statutes:
            if len(statutes_by_id) >= 6:
                break
            statutes_by_id.setdefault(row["chunk_id"], dict(row))

        statutes = list(statutes_by_id.values())[:6]

        # 2. Retrieve top precedent cases (prioritizing Supreme Court + high section_priority chunks)
        j_dom_clause = (
            "AND c.domain IN ('ni_act_138', 'contract_breach', 'both')"
            if resolved_domain in ("both", "constitution")
            else "AND c.domain IN (?, 'both')"
        )
        j_params = [fts_expr] if resolved_domain in ("both", "constitution") else [fts_expr, resolved_domain]
        chunk_hits = conn.execute(
            f"""
            SELECT jc.chunk_id, jc.case_id, jc.chunk_index, jc.section_type, jc.section_priority,
                   jc.text, c.court, c.court_type, c.bench_strength, c.title, c.citation,
                   c.case_number, c.decision_date, c.year, c.disposition, c.hierarchy_weight,
                   bm25(f.legal_fts) AS bm25_score
            FROM legal_fts f
            JOIN judgment_chunks jc ON jc.chunk_id = f.item_id
            JOIN judgment_cases c ON c.case_id = jc.case_id
            WHERE f.legal_fts MATCH ? AND f.category = 'judgment' {j_dom_clause}
            ORDER BY (bm25(f.legal_fts) - (c.hierarchy_weight * 0.035) - (jc.section_priority * 0.02)) ASC
            LIMIT 40
            """,
            j_params,
        ).fetchall()

        selected_cases: dict[str, dict] = {}
        for row in chunk_hits:
            cid = row["case_id"]
            if cid not in selected_cases:
                if len(selected_cases) >= 5:
                    continue
                cites = [
                    r["target_ref"]
                    for r in conn.execute(
                        "SELECT target_ref FROM case_citations WHERE source_case_id = ? LIMIT 5",
                        (cid,),
                    ).fetchall()
                ]
                # Also fetch the case's highest-priority ratio/conclusion/arguments chunk if different
                best_chunks = conn.execute(
                    """
                    SELECT chunk_index, section_type, section_priority, text
                    FROM judgment_chunks
                    WHERE case_id = ?
                    ORDER BY CASE
                        WHEN section_type IN ('ratio_decidendi', 'conclusion', 'judgment', 'analysis') THEN 2
                        WHEN section_type IN ('arguments', 'issues', 'facts') THEN 1
                        ELSE 0
                    END DESC, section_priority DESC, chunk_index ASC
                    LIMIT 2
                    """,
                    (cid,),
                ).fetchall()
                excerpts = [_clean_excerpt(row["text"], 210)]
                for b in best_chunks:
                    ex = _clean_excerpt(b["text"], 180)
                    if ex and ex not in excerpts and len(excerpts) < 2:
                        excerpts.append(ex)
                selected_cases[cid] = {
                    "case_id": cid,
                    "title": row["title"] or cid,
                    "court": row["court"] or "High Court",
                    "court_type": row["court_type"] or "high_court",
                    "bench_strength": int(row["bench_strength"] or 1),
                    "year": row["year"],
                    "decision_date": (row["decision_date"] or "")[:10],
                    "citation": row["citation"] or row["case_number"] or cid,
                    "disposition": row["disposition"] or "DECIDED",
                    "section_type": row["section_type"] or "judgment",
                    "citations_extracted": cites,
                    "excerpts": excerpts,
                }

    precedents = list(selected_cases.values())

    # 3. Format the verbatim-quote-friendly Indian Legal Source Dossier within max_chars
    lines = [
        f"INDIAN JURISDICTION LEGAL DOSSIER (Open India Law v2026.08.1 — {DOMAIN_LABELS.get(resolved_domain, resolved_domain)})",
        "Court Hierarchy & Precedent Rule: Under Article 141 of the Constitution of India, law declared by the Supreme Court of India is binding on all High Courts and subordinate courts. A larger Bench binds a smaller or co-ordinate Bench.",
        "",
        "=== I. APPLICABLE STATUTORY, CONSTITUTIONAL & REGULATORY PROVISIONS ===",
    ]
    for idx, st in enumerate(statutes, 1):
        flags = []
        if st.get("has_proviso"):
            flags.append("HAS_PROVISO_EXCEPTION")
        if st.get("has_non_obstante"):
            flags.append("NON_OBSTANTE_OVERRIDE")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        sec_label = st.get("section_number") or "Provision"
        lines.append(
            f"[{idx}] {st.get('title')} — Section/Article {sec_label} ({st.get('act_status') or 'in_force'}){flag_str}: "
            f"{_clean_excerpt(st.get('text') or '', 200)}"
        )

    lines.append("")
    lines.append("=== II. BINDING SUPREME COURT & HIGH COURT PRECEDENTS ===")
    for idx, pr in enumerate(precedents, 1):
        cite_str = f" | Cited authorities: {', '.join(pr['citations_extracted'][:3])}" if pr["citations_extracted"] else ""
        lines.append(
            f"[P{idx}] {pr['title']} ({pr['citation']}) — {pr['court']} "
            f"(Bench strength: {pr['bench_strength']}, Date: {pr['decision_date'] or pr['year']}, Disposition: {pr['disposition']}{cite_str}): "
            + _clean_excerpt(" ".join(pr["excerpts"]), 220)
        )

    dossier = "\n".join(lines).strip()
    if len(dossier) > max_chars:
        dossier = dossier[: max_chars - 1].rsplit(" ", 1)[0] + "."

    return {
        "domain": resolved_domain,
        "domain_label": DOMAIN_LABELS.get(resolved_domain, resolved_domain),
        "scenario": effective_scenario,
        "source": dossier,
        "statutes_count": len(statutes),
        "precedents_count": len(precedents),
        "statutes": [
            {
                "chunk_id": s["chunk_id"],
                "title": s["title"],
                "section_number": s["section_number"],
                "has_proviso": bool(s["has_proviso"]),
                "has_non_obstante": bool(s["has_non_obstante"]),
            }
            for s in statutes
        ],
        "precedents": [
            {
                "case_id": p["case_id"],
                "title": p["title"],
                "court": p["court"],
                "court_type": p["court_type"],
                "bench_strength": p["bench_strength"],
                "year": p["year"],
                "citation": p["citation"],
                "disposition": p["disposition"],
                "citations_extracted": p["citations_extracted"],
            }
            for p in precedents
        ],
    }


def retrieve_turn_authorities(
    scenario: str,
    recent_lines: list[str],
    speaker_role: str = "",
    db_path: Path = DEFAULT_LEGAL_DB,
    limit_statutes: int = 3,
    limit_precedents: int = 3,
) -> dict:
    """Live per-turn RAG lookup over legal_poc.db triggered by the opponent's latest courtroom statements."""
    path = ensure_legal_db(Path(db_path))
    if not path.exists():
        return {"authorities": [], "citations": []}

    focus_text = " ".join(recent_lines[-3:]) if recent_lines else scenario
    combined = f"{focus_text} {scenario}"
    domain = detect_legal_domain(combined, "auto")
    fts_expr = _fts_expression(focus_text or scenario)
    prefer_exceptions = any(k in (speaker_role or "").lower() for k in ("defense", "respondent", "accused", "opposite"))

    authorities: list[dict] = []
    citations: list[str] = []
    try:
        with closing(sqlite3.connect(path)) as conn:
            conn.row_factory = sqlite3.Row
            dom_clause = (
                "AND l.domain IN ('ni_act_138', 'contract_breach', 'both', 'constitution')"
                if domain == "both"
                else "AND l.domain IN (?, 'both', 'constitution')"
            )
            dom_params = [fts_expr] if domain == "both" else [fts_expr, domain]
            proviso_boost = " - (l.has_proviso * 1.5) - (l.has_non_obstante * 1.0)" if prefer_exceptions else ""
            stat_rows = conn.execute(
                f"""
                SELECT l.chunk_id, l.title, l.section_number, l.has_proviso, l.has_non_obstante, l.text
                FROM legal_fts f
                JOIN legislation_provisions l ON l.chunk_id = f.item_id
                WHERE f.legal_fts MATCH ? AND f.category = 'legislation' {dom_clause}
                ORDER BY (bm25(f.legal_fts){proviso_boost}) ASC
                LIMIT ?
                """,
                [*dom_params, max(1, limit_statutes)],
            ).fetchall()
            for r in stat_rows:
                sec = r["section_number"] or "Provision"
                label = f"{r['title']} s.{sec}" if not str(sec).startswith("Article") else f"{r['title']} {sec}"
                flags = []
                if r["has_proviso"]:
                    flags.append("proviso/exception")
                if r["has_non_obstante"]:
                    flags.append("non-obstante")
                authorities.append({
                    "kind": "statute",
                    "citation": label,
                    "flags": flags,
                    "excerpt": _clean_excerpt(r["text"], 320),
                })
                if label not in citations:
                    citations.append(label)

            j_dom_clause = (
                "AND c.domain IN ('ni_act_138', 'contract_breach', 'both')"
                if domain in ("both", "constitution")
                else "AND c.domain IN (?, 'both')"
            )
            j_params = [fts_expr] if domain in ("both", "constitution") else [fts_expr, domain]
            sec_pref = (
                "WHEN jc.section_type IN ('arguments', 'ratio_decidendi', 'analysis', 'conclusion') THEN 2"
                if prefer_exceptions
                else "WHEN jc.section_type IN ('ratio_decidendi', 'conclusion', 'judgment', 'analysis') THEN 2"
            )
            case_rows = conn.execute(
                f"""
                SELECT jc.case_id, jc.section_type, jc.text, c.title, c.court, c.bench_strength,
                       c.year, c.citation, c.case_number, c.disposition
                FROM legal_fts f
                JOIN judgment_chunks jc ON jc.chunk_id = f.item_id
                JOIN judgment_cases c ON c.case_id = jc.case_id
                WHERE f.legal_fts MATCH ? AND f.category = 'judgment' {j_dom_clause}
                ORDER BY (
                    bm25(f.legal_fts)
                    - (c.hierarchy_weight * 0.035)
                    - (CASE {sec_pref} ELSE 0 END)
                ) ASC
                LIMIT 18
                """,
                j_params,
            ).fetchall()
            seen_cases: set[str] = set()
            for r in case_rows:
                cid = r["case_id"]
                if cid in seen_cases:
                    continue
                seen_cases.add(cid)
                cite_ref = r["citation"] or r["case_number"] or cid
                label = f"{r['title']} ({cite_ref}, {r['court']}, Bench: {r['bench_strength']}, {r['Disposition' if 'Disposition' in r.keys() else 'disposition'] or 'DECIDED'})"
                short_cite = f"{(r['title'] or cid)[:48]} ({cite_ref}, {r['court']})"
                authorities.append({
                    "kind": "precedent",
                    "citation": label,
                    "section_type": r["section_type"],
                    "excerpt": _clean_excerpt(r["text"], 340),
                })
                if short_cite not in citations:
                    citations.append(short_cite)
                if len(seen_cases) >= limit_precedents:
                    break
    except sqlite3.Error:
        return {"authorities": [], "citations": []}

    return {"authorities": authorities, "citations": citations}

