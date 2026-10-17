import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

import pyarrow.parquet as pq

from legisimate.core import Config
from legisimate.court import court_calls, court_role_for_slot, run_court, schedule_court
from legisimate.legal import ensure_legal_db, legal_status, retrieve_legal_dossier, retrieve_turn_authorities
from legisimate.server import Manager, Store
from scripts.extract_open_india_law import search_legal_corpus
from test_core import FakeModel, FixtureEngine

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "open_india_law"


class OpenIndiaLawExtractionTests(unittest.TestCase):
    def test_extracted_artifacts_and_manifest(self):
        manifest_path = DATA_DIR / "extraction_manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["dataset"], "open-india-law")
        self.assertEqual(manifest["version"], "v2026.08.1")
        for key in ("target_legislation_parquet", "domain_judgments_parquet"):
            artifact = Path(manifest["outputs"][key])
            self.assertTrue(artifact.exists(), f"Missing artifact {artifact}")
            self.assertGreater(artifact.stat().st_size, 100_000)
        db_path = ensure_legal_db(DATA_DIR / "legal_poc.db")
        self.assertTrue(db_path.exists())

    def test_legislation_slice_completeness(self):
        table = pq.read_table(DATA_DIR / "target_legislation.parquet")
        rows = table.to_pylist()
        self.assertGreaterEqual(len(rows), 7000)
        self.assertTrue(all(r["language_code"] == "en" for r in rows))

        act_ids = {r["act_id"] for r in rows}
        for required_act in (
            "IND_constitution_1950",
            "IND_central_2189",  # Negotiable Instruments Act, 1881
            "IND_central_2187",  # Indian Contract Act, 1872
            "IND_central_1583",  # Specific Relief Act, 1963
            "IND_central_1565",  # Limitation Act, 1963
            "IND_central_2082",  # Payment and Settlement Systems Act, 2007
        ):
            self.assertIn(required_act, act_ids)

        ni_sections = {str(r["section_number"]) for r in rows if r["act_id"] == "IND_central_2189"}
        self.assertIn("138", ni_sections)
        self.assertIn("139", ni_sections)
        self.assertIn("141", ni_sections)
        self.assertIn("142", ni_sections)

        contract_sections = {str(r["section_number"]) for r in rows if r["act_id"] == "IND_central_2187"}
        self.assertIn("56", contract_sections)
        self.assertIn("73", contract_sections)
        self.assertIn("74", contract_sections)

        const_articles = {str(r["section_number"]) for r in rows if r["act_id"] == "IND_constitution_1950"}
        self.assertIn("Article 32", const_articles)
        self.assertIn("Article 136", const_articles)
        self.assertIn("Article 141", const_articles)
        self.assertIn("Article 226", const_articles)

    def test_whole_case_judgment_integrity(self):
        table = pq.read_table(DATA_DIR / "domain_judgments.parquet")
        rows = table.to_pylist()
        self.assertGreaterEqual(len(rows), 5000)
        self.assertTrue(all(r["language_code"] == "en" for r in rows))

        courts = {r["court"] for r in rows}
        self.assertIn("Supreme Court of India", courts)
        self.assertTrue(any("Delhi" in c for c in courts))
        self.assertTrue(any("Bombay" in c for c in courts))

        by_case = {}
        for row in rows:
            by_case.setdefault(row["case_id"], []).append(row)
        self.assertGreaterEqual(len(by_case), 1000)

        for case_id, chunks in by_case.items():
            indices = [int(c["chunk_index"]) for c in chunks]
            expected_total = int(chunks[0]["total_chunks"])
            self.assertEqual(
                indices,
                list(range(expected_total)),
                f"Fragmented chunks for {case_id}: got {indices}, expected 0..{expected_total - 1}",
            )

    def test_sqlite_fts5_retrieval_and_citations(self):
        db_path = DATA_DIR / "legal_poc.db"
        self.assertTrue(db_path.exists())
        with closing(sqlite3.connect(db_path)) as conn:
            citation_count = conn.execute("SELECT COUNT(*) FROM case_citations").fetchone()[0]
            self.assertGreater(citation_count, 5000)

        ni_hits = search_legal_corpus(
            db_path,
            "Section 138 Negotiable Instruments Act dishonour of cheque statutory notice security cheque",
            domain="ni_act_138",
            limit=12,
        )
        self.assertTrue(ni_hits)
        self.assertTrue(any("138" in h["snippet"] or "138" in h["title"] for h in ni_hits))

        contract_hits = search_legal_corpus(
            db_path,
            "Section 73 Section 74 Indian Contract Act breach of contract liquidated damages",
            domain="contract_breach",
            limit=12,
        )
        self.assertTrue(contract_hits)
        self.assertTrue(any("73" in h["snippet"] or "74" in h["snippet"] or "breach" in h["snippet"].lower() for h in contract_hits))

    def test_legal_dossier_builder_for_simulator(self):
        status = legal_status()
        self.assertTrue(status["available"])
        self.assertGreaterEqual(status["legislation_provisions"], 7000)
        self.assertGreaterEqual(status["judgment_cases"], 1500)

        for domain in ("ni_act_138", "contract_breach", "constitution"):
            dossier = retrieve_legal_dossier("", domain=domain)
            self.assertEqual(dossier["domain"], domain)
            self.assertTrue(dossier["scenario"])
            self.assertGreaterEqual(dossier["statutes_count"], 4)
            self.assertGreaterEqual(dossier["precedents_count"], 3)
            self.assertLessEqual(len(dossier["source"]), 5400)
            self.assertIn("Article 141", dossier["source"])
            self.assertIn("=== I. APPLICABLE STATUTORY", dossier["source"])
            self.assertIn("=== II. BINDING SUPREME COURT & HIGH COURT PRECEDENTS ===", dossier["source"])

    def test_courtroom_simulation_with_live_rag_and_jury_bench_verdict(self):
        import tempfile

        rag = retrieve_turn_authorities(
            "Dishonour of security cheque under Section 138 Negotiable Instruments Act",
            ["Defense Counsel: The cheque was given as a security deposit and stop payment was issued due to defective goods."],
            speaker_role="Complainant / Plaintiff Lead Counsel",
        )
        self.assertTrue(rag["authorities"])
        self.assertTrue(rag["citations"])

        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "runs.db")
            model = FakeModel()
            manager = Manager(store, model, engine=FixtureEngine(model))
            run = manager.create({
                "scenario": "Cheque dishonour under Section 138 NI Act for a security cheque after stop-payment instructions.",
                "agent_count": 8,
                "rounds": 3,
                "platform_mode": "court",
                "conversation_minutes": 6,
            })
            manager.worker.join(5)
            prepared = store.get(run["id"])
            self.assertEqual(prepared["status"], "ready")
            self.assertIn("INDIAN JURISDICTION LEGAL DOSSIER", prepared["config"]["source"])
            roles = [a["role"] for a in prepared["agents"]]
            self.assertEqual(roles[0], court_role_for_slot(1))  # Presiding Judge (Bench)
            self.assertIn("Complainant / Plaintiff Lead Counsel", roles)
            self.assertIn("Accused / Respondent Defense Counsel", roles)
            self.assertTrue(any("Jury" in r for r in roles))

            manager.start(run["id"])
            manager.worker.join(10)
            finished = store.get(run["id"])
            self.assertEqual(finished["status"], "completed")
            court_actions = [a for a in finished["actions"] if a.get("platform") == "court"]
            self.assertEqual(
                len(court_actions),
                court_calls(Config.model_validate(finished["config"]), [
                    type("Obj", (), {"id": a["id"], "role": a["role"]}) for a in finished["agents"]
                ]),
            )
            self.assertTrue(all(a["data"].get("rag_citations") for a in court_actions))
            self.assertTrue(all(a["data"].get("tactical_move") and a["data"].get("counter_strategy") for a in court_actions))
            # Final turn of the final branch is delivered by the Presiding Judge (agent_id == 1)
            self.assertEqual(court_actions[-1]["agent_id"], 1)
            self.assertIn("Future #3", court_actions[-1]["data"]["stage"])
            court_payloads = [p for p in model.payloads if "live_rag_authorities" in p]
            self.assertTrue(court_payloads and all(p["live_rag_authorities"] for p in court_payloads))


if __name__ == "__main__":
    unittest.main()
