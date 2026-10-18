import json
import unittest
import tempfile
from pathlib import Path

from pydantic import ValidationError

from legisimate.casework import (CaseFacts, CaseRequest, CaseWorkbench, assess_timeline, build_hearing,
                              CaseStatement, export_brief, grounded_statement_schema,
                              read_authority, resolve_source_quotes, search_authorities, verify_quotes)


class TimelineTests(unittest.TestCase):
    def check_by_id(self, result, identity):
        return next(item for item in result["checks"] if item["id"] == identity)

    def test_missing_dates_never_create_deadlines_or_passes(self):
        result = assess_timeline({}, "2026-10-17")
        self.assertEqual(result["deadlines"], [])
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["missing"], 5)

    def test_notice_boundary_excludes_receipt_day(self):
        facts = {"memo_received_on": "2026-09-01", "notice_sent_on": "2026-10-01"}
        result = assess_timeline(facts, "2026-10-17")
        self.assertEqual(self.check_by_id(result, "notice")["status"], "checked")
        facts["notice_sent_on"] = "2026-10-02"
        self.assertEqual(self.check_by_id(assess_timeline(facts, "2026-10-17"), "notice")["status"], "attention")

    def test_payment_period_and_premature_complaint(self):
        facts = {"notice_received_on": "2026-10-01", "complaint_filed_on": "2026-10-16"}
        result = assess_timeline(facts, "2026-10-16")
        self.assertEqual(self.check_by_id(result, "payment")["status"], "attention")
        self.assertIn("before", self.check_by_id(result, "filing")["detail"])
        self.assertEqual(result["deadlines"][1]["date"], "2026-11-17")

    def test_calendar_month_not_thirty_days_and_condonation(self):
        facts = {"notice_received_on": "2026-01-15", "complaint_filed_on": "2026-03-01"}
        result = assess_timeline(facts, "2026-03-02")
        self.assertEqual(result["deadlines"][1]["date"], "2026-02-28")
        self.assertIn("condonation", self.check_by_id(result, "filing")["detail"])

    def test_dates_must_be_valid_and_chronological(self):
        for facts in ({"memo_received_on": "2026-02-30"},
                      {"memo_received_on": "2026-10-10", "notice_sent_on": "2026-10-01"},
                      {"cheque_date": "2026-1-01"}):
            with self.assertRaises(ValidationError):
                CaseFacts.model_validate(facts)

    def test_consent_is_required(self):
        with self.assertRaises(ValidationError):
            CaseRequest(scenario="A cheque was returned unpaid after a supply dispute.")

    def test_debt_records_are_not_authenticated_by_a_date_check(self):
        result = assess_timeline({"debt_evidence": "available"}, "2026-10-17")
        self.assertIn("not independently authenticated", self.check_by_id(result, "debt")["detail"])

    def test_assessment_date_is_iso_and_completed_events_cannot_be_future(self):
        for as_of in ("20261017", "2026-W42-6"):
            with self.assertRaises(ValueError):
                assess_timeline({}, as_of)
        for field in ("cheque_date", "presented_on", "memo_received_on", "notice_sent_on", "notice_received_on", "complaint_filed_on"):
            with self.assertRaisesRegex(ValueError, "assessment date"):
                assess_timeline({field: "2026-10-18"}, "2026-10-17")
        self.assertEqual(assess_timeline({"valid_until": "2026-11-01"}, "2026-10-17")["checked"], 0)


class CaseModel:
    name = "case-fixture"

    def __init__(self):
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.calls = 0
        self.call_limit = 500
        self.payloads = []

    def generate(self, schema, instructions, payload, budget, **kwargs):
        if self.calls >= self.call_limit:
            raise ValueError("model_call_budget")
        self.calls += 1
        self.payloads.append(json.loads(json.dumps(payload)))
        if schema.__name__ == "ResearchDecision":
            return schema(tool="search_precedents" if payload["step"] == 1 else "finish",
                          query="security cheque legally enforceable debt Section 138", source_id="")
        if schema.__name__ == "CasePlan":
            return schema(branches=[{"title": title, "question": "Is the liability supported under Section 138?",
                                    "assumptions": [], "evidence_needed": ["Obtain the bank memo"]}
                                   for title in ("Notice and service", "Debt and payment", "Settlement and records")])
        if schema.__name__ == "CaseStatement":
            source = payload["sources"][0]
            return schema(text="The supplied facts require documentary support.", what_to_say="Request the bank memo.",
                          why_it_matters="Dates need to be established.", assessment="needs_evidence",
                          citations=[{"source_id": source["id"], "quote_id": source["quote_options"][0]["id"]}])
        return schema(summary="Further documents are required.", recommended_branch=1,
                      recommendation_reason="Resolve the notice question first.", next_steps=["Obtain the return memo"],
                      questions_for_lawyer=["Was notice validly served?"], settlement_option="Discuss a voluntary resolution.",
                      limitations="Not legal advice. The dates are unconfirmed.")


class CaseWorkflowTests(unittest.TestCase):
    def test_hearing_options_are_bounded_and_schedule_both_sides(self):
        body = {"scenario": "A supplier's security cheque was returned unpaid after a dispute.", "consent": True}
        for side in ("complainant", "respondent"):
            for rebuttals in (1, 2, 3):
                for panel in (0, 1, 3):
                    request = CaseRequest(**body, side=side, rebuttal_rounds=rebuttals, review_panel_size=panel)
                    actors, steps = build_hearing(request)
                    self.assertEqual(len(actors), 9 + panel)
                    self.assertEqual(len(steps), 14 + 4 * rebuttals + panel)
                    self.assertEqual([step["speaker"] for step in steps[:3]], [1, 3, 2] if side == "complainant" else [1, 2, 3])
                    self.assertEqual(steps[-1]["phase"], "Bench assessment")
                    self.assertEqual(sum(step["phase"] == "Educational review" for step in steps), panel)
                    self.assertTrue(all(1 <= step["speaker"] <= len(actors) for step in steps))
        for field, invalid in (("rebuttal_rounds", 0), ("rebuttal_rounds", 4), ("rebuttal_rounds", True),
                               ("review_panel_size", -1), ("review_panel_size", 4), ("review_panel_size", 1.5)):
            with self.assertRaises(ValidationError):
                CaseRequest(**body, **{field: invalid})

    def test_full_hearing_has_parties_witnesses_and_rebuttals(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = CaseWorkbench(Path(directory) / "cases.db", CaseModel())
            run = manager.create({"scenario": "A supplier's security cheque was returned unpaid after a dispute.", "consent": True})
            manager.worker.join(15)
            saved = manager.get(run["id"])
            self.assertEqual(saved["status"], "completed")
            self.assertEqual(saved["config"]["agent_count"], 9)
            self.assertTrue({"Complainant (Party)", "Accused (Party)", "Complainant Witness", "Defence Witness"}
                            .issubset({actor["role"] for actor in saved["agents"]}))
            self.assertEqual(saved["planned_turns"], 66)
            self.assertEqual(saved["config"]["model_call_budget"], 72)
            self.assertLessEqual(saved["model_calls"], saved["config"]["model_call_budget"])
            for branch in saved["branches"]:
                self.assertEqual(len(branch["turns"]), 22)
                self.assertEqual(branch["turns"][0]["role"], "Presiding Magistrate")
                self.assertEqual(branch["turns"][-1]["role"], "Presiding Magistrate")
                self.assertEqual({turn["data"]["phase"] for turn in branch["turns"]},
                                 {"Opening arguments", "Party statements", "Witness examination", "Rebuttals", "Bench assessment"})
                self.assertGreaterEqual(sum(turn["role"] == "Complainant Counsel" for turn in branch["turns"]), 4)
                self.assertGreaterEqual(sum(turn["role"] == "Respondent Defense Counsel" for turn in branch["turns"]), 4)
                self.assertIsNone(branch["turns"][0]["data"]["reply_to"])
                self.assertEqual([turn["data"]["reply_to"] for turn in branch["turns"][1:]],
                                 [turn["id"] for turn in branch["turns"][:-1]])

    def test_statement_schema_binds_exact_passages_to_their_source(self):
        sources = [{"id": "notice", "text": "A written notice must follow the specified statutory timing."},
                   {"id": "service", "text": "Proof of effective service must be established independently."}]
        schema, prompt_sources = grounded_statement_schema(sources)
        self.assertTrue(all(source["quote_options"] for source in prompt_sources))
        fields = {"text": "Check the notice.", "what_to_say": "Obtain dispatch records.",
                  "why_it_matters": "Service remains unconfirmed.", "assessment": "needs_evidence"}
        for source_id, quote_id in (("notice", prompt_sources[1]["quote_options"][0]["id"]), ("notice", "invented-quote")):
            with self.assertRaises(ValidationError):
                schema(**fields, citations=[{"source_id": source_id, "quote_id": quote_id}])
        result = schema(**fields, citations=[{"source_id": "notice", "quote_id": prompt_sources[0]["quote_options"][0]["id"]}])
        resolved = resolve_source_quotes(result.citations, prompt_sources)
        self.assertTrue(verify_quotes(resolved, sources)[0]["matched"])
        self.assertEqual(resolved[0].quote, sources[0]["text"])
        mixed = schema(**fields, citations=[{"source_id": "notice", "quote_id": prompt_sources[0]["quote_options"][0]["id"]},
                                            {"source_id": "unoffered_case", "quote_id": prompt_sources[1]["quote_options"][0]["id"]}])
        self.assertEqual([citation.source_id for citation in mixed.citations], ["notice"])

    def test_court_statements_require_at_least_one_source_quote(self):
        with self.assertRaises(ValidationError):
            CaseStatement(text="A claim", what_to_say="A response", why_it_matters="An issue",
                          assessment="needs_evidence", citations=[])

    def test_quote_matching_does_not_accept_unknown_or_empty_sources(self):
        source = {"id": "known", "text": "The payee must confirm the actual date of receipt."}
        result = verify_quotes([
            {"source_id": "known", "quote": source["text"]},
            {"source_id": "unknown", "quote": source["text"]},
            {"source_id": "known", "quote": ""},
            {"source_id": "known", "quote": "A completely invented legal proposition."}], [source])
        self.assertEqual([item["matched"] for item in result], [True, False, False, False])
        self.assertIn("interpretation is not verified", result[0]["note"])

    def test_real_corpus_tools_return_resolvable_records(self):
        for kind in ("statute", "precedent"):
            records = search_authorities("Section 138 security cheque legally enforceable debt", kind)
            self.assertTrue(records)
            for record in records:
                self.assertEqual(read_authority(record["id"])["id"], record["id"])
        self.assertIsNone(read_authority("unknown' OR 1=1 --"))

    def test_end_to_end_branches_are_isolated_and_locally_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            model = CaseModel()
            manager = CaseWorkbench(Path(directory) / "cases.db", model)
            run = manager.create({"scenario": "A supplier's security cheque was returned unpaid after a dispute.", "consent": True})
            manager.worker.join(10)
            self.assertFalse(manager.worker.is_alive())
            saved = manager.get(run["id"])
            self.assertEqual(saved["status"], "completed")
            self.assertEqual(len(saved["branches"]), 3)
            self.assertEqual(len(saved["actions"]), 66)
            self.assertEqual(saved["citation_check"], {"matched": 66, "total": 66})
            self.assertTrue(any(item["tool"] == "search_precedents" for item in saved["trace"]))
            starts = [payload for payload in model.payloads if payload.get("turn_number") == 1]
            self.assertEqual(len(starts), 3)
            self.assertTrue(all(not payload["conversation"] for payload in starts))
            self.assertEqual(saved["timeline"]["checked"], 0)
            self.assertIn("quote matched", export_brief(saved))
            self.assertIn(saved["request"]["as_of"], export_brief(saved))
            self.assertIn("text provenance only", export_brief(saved))
            self.assertEqual(manager.list()[0]["id"], run["id"])
            self.assertIsNone(manager.active)

    def test_failure_and_restart_do_not_erase_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.db"
            manager = CaseWorkbench(path, CaseModel())
            run = {"id": "saved", "status": "researching", "sources": [{"id": "kept"}]}
            manager.save(run)
            restarted = CaseWorkbench(path, CaseModel())
            self.assertEqual(restarted.get("saved")["status"], "interrupted")
            self.assertEqual(restarted.get("saved")["sources"], [{"id": "kept"}])

    def test_supported_model_assessment_cannot_clear_missing_inputs(self):
        class SupportiveModel(CaseModel):
            def generate(self, schema, *args, **kwargs):
                result = super().generate(schema, *args, **kwargs)
                if schema.__name__ == "CaseStatement":
                    result = schema.model_validate({**result.model_dump(), "assessment": "supported"})
                return result
        with tempfile.TemporaryDirectory() as directory:
            manager = CaseWorkbench(Path(directory) / "cases.db", SupportiveModel())
            run = manager.create({"scenario": "A supplier's security cheque was returned unpaid after a dispute.", "consent": True})
            manager.worker.join(10)
            saved = manager.get(run["id"])
            self.assertEqual(saved["status"], "completed")
            self.assertTrue(all(turn["assessment"] == "needs_evidence" and turn["guardrails"] for turn in saved["actions"]))
            self.assertIn("Caution: Missing", export_brief(saved))

    def test_provider_failure_keeps_research_and_releases_gate(self):
        class FailingModel(CaseModel):
            def generate(self, schema, *args, **kwargs):
                if schema.__name__ == "CasePlan":
                    raise RuntimeError("sensitive provider detail must not be returned")
                return super().generate(schema, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            manager = CaseWorkbench(Path(directory) / "cases.db", FailingModel())
            run = manager.create({"scenario": "A supplier's security cheque was returned unpaid after a dispute.", "consent": True})
            manager.worker.join(10)
            saved = manager.get(run["id"])
            self.assertEqual(saved["status"], "failed")
            self.assertTrue(saved["sources"])
            self.assertTrue(saved["trace"])
            self.assertNotIn("sensitive", saved["error"])
            self.assertIsNone(manager.active)

    def test_cancel_retains_sources_and_releases_gate(self):
        import threading
        entered, released = threading.Event(), threading.Event()
        class WaitingModel(CaseModel):
            def generate(self, schema, *args, **kwargs):
                entered.set()
                released.wait(5)
                if kwargs["cancelled"]():
                    raise ValueError("cancelled")
                return super().generate(schema, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            manager = CaseWorkbench(Path(directory) / "cases.db", WaitingModel())
            run = manager.create({"scenario": "A supplier's security cheque was returned unpaid after a dispute.", "consent": True})
            try:
                self.assertTrue(entered.wait(5))
                manager.cancel(run["id"])
            finally:
                released.set()
                manager.worker.join(10)
            saved = manager.get(run["id"])
            self.assertEqual(saved["status"], "cancelled")
            self.assertTrue(saved["sources"])
            self.assertIsNone(manager.active)


if __name__ == "__main__":
    unittest.main()