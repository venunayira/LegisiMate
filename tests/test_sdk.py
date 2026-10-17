"""Exercise the installed SDK over real localhost HTTP; no paid model or app demo mode."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openai import OpenAI

from legisimate.core import Config, Model, generate_report, prepare, run_round


class ProviderFixture(BaseHTTPRequestHandler):
    requests = []
    pacing = 0
    tool_factory = None

    def log_message(self, *_):
        pass

    def do_POST(self):
        if self.path.endswith("/chat/completions"):
            return ChatProviderFixture.do_POST(self)
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.requests.append(request)
        name = request["text"]["format"]["name"]
        payload = json.loads(request["input"])
        if name == "Ontology":
            result = {"entity_types": ["person", "organization", "issue"],
                      "actor_types": ["person", "organization"], "relationship_types": ["works_at", "concerns"]}
        elif name == "GraphBatch":
            quote = (payload.get("evidence_excerpts") or [payload["text"][:400]])[0]
            reference = [{"source_id": payload["source_id"], "quote": quote}]
            result = {"nodes": [{"id": "library", "name": "Town Library", "kind": "organization",
                "summary": "Library services and opening hours.", "synthetic": payload["hypothetical"], "evidence": reference},
                {"id": "resident", "name": "Local Residents", "kind": "person", "summary": "Residents use the library.",
                 "synthetic": payload["hypothetical"], "evidence": reference}], "edges": [
                {"source": "resident", "target": "library", "kind": "concerns", "fact": "Residents discuss access.",
                 "synthetic": payload["hypothetical"], "evidence": reference}]}
        elif name == "PopulationBatch":
            result = {"agents": [{"name": ["Elin", "Boris", "Mira", "Jonas"][slot["index"]%4] + f" {slot['index']}",
                "role": "Resident" if slot["index"]%2 else "Library Director", "perspective": "Concerned about affordable access.",
                "profile": {"entity_id": slot["entity_id"], "goal": "Protect reliable access.",
                    "background": "A synthetic stakeholder balancing work and community responsibilities.",
                    "interests": ["access", "funding"], "beliefs": ["Costs need a public explanation."],
                    "speaking_style": "Direct and specific.", "source_entity_ids": [record["id"] for record in payload["graph"]["nodes"]],
                    "activity_level": 1.0, "active_hours": list(range(24)),
                    "outlook": ["optimistic", "pessimistic", "skeptical", "pragmatic"][slot["index"] % 4],
                    "openness": ["low", "medium", "high"][slot["index"] % 3],
                    "initial_view": "Access matters, but I need to see who pays."}} for slot in payload["slots"]]}
        elif name == "Personas":
            result = {"agents": [{"name": f"Persona {i}", "role": "Resident",
                                   "perspective": "Concerned about affordable access"}
                                  for i in range(1, payload["agent_count"] + 1)]}
        elif name == "Utterance":
            result = {"text": "I hear you, but who pays for the extra evening staff? Can we phase it in?",
                      "view": "Longer hours are worth it if the funding is phased and public.",
                      "shift": "softened" if payload["memories"] else "unchanged"}
        elif name == "CourtUtterance":
            result = {"text": "My Lady, under Section 139 read with binding Supreme Court authority, the cheque carries a statutory presumption.",
                      "view": "The statutory presumption holds if the notice timeline is proved.",
                      "shift": "softened" if payload["memories"] else "unchanged",
                      "if_opponent_argues": "If Defense claims the cheque was a security deposit.",
                      "tactical_move": "Invoke Section 139 NI Act and prove crystallized debt on presentation date.",
                      "counter_strategy": "Cite Supreme Court precedent holding security cheques attract Section 138 once liability matures.",
                      "branch_outcome": "complainant_favour",
                      "win_probability": 75}
        elif name == "Action":
            result = {"kind": "reply" if payload.get('reply_to') else "post",
                      "text": "I hear your concern about hours, but affordable access still needs a concrete plan.",
                      "stance": "neutral", "reply_to": payload.get('reply_to')}
        else:
            result = {"summary": "Participants discussed access.", "findings": [
                {"claim": "Affordable access was raised.", "action_ids": [payload["actions"][0]["id"]]}],
                      "limitations": "Fictional personas; not a calibrated prediction.",
                      "conclusion":"Access remains the shared concern, while how to fund it is unresolved.",
                      "agreements":["Access matters."],"disagreements":["How to fund the policy."],
                      "open_questions":["Who bears the cost?"]}
            if name == "GroundedReport":
                result["opinion_changes"] = ["Several residents softened after hearing about phased funding."]
        response = {"id": "resp_fixture", "object": "response", "created_at": 1,
                    "status": "completed", "model": request["model"],
                    "output": [{"type": "message", "id": "msg_fixture", "status": "completed",
                                "role": "assistant", "content": [{"type": "output_text", "annotations": [],
                                                                      "text": json.dumps(result)}]}],
                    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}
        if request.get('stream'):
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Connection','close')
            self.end_headers()
            sequence = 0
            def event(kind, **fields):
                nonlocal sequence
                body = {'type':kind,'sequence_number':sequence, **fields}
                sequence += 1
                self.wfile.write(f"event: {kind}\ndata: {json.dumps(body)}\n\n".encode()); self.wfile.flush()
            message = response['output'][0]
            text = message['content'][0]['text']
            try:
                event('response.created',response={**response,'status':'in_progress','output':[],'usage':None})
                event('response.output_item.added',output_index=0,item={**message,'status':'in_progress','content':[]})
                event('response.content_part.added',item_id='msg_fixture',output_index=0,content_index=0,
                      part={'type':'output_text','annotations':[],'text':''})
                for start in range(0,len(text),15):
                    event('response.output_text.delta',item_id='msg_fixture',output_index=0,content_index=0,
                          delta=text[start:start+15],logprobs=[])
                    if self.pacing:
                        threading.Event().wait(self.pacing)
                event('response.output_text.done',item_id='msg_fixture',output_index=0,content_index=0,text=text,logprobs=[])
                event('response.content_part.done',item_id='msg_fixture',output_index=0,content_index=0,part=message['content'][0])
                event('response.output_item.done',output_index=0,item=message)
                event('response.completed',response=response)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        body = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ChatProviderFixture(ProviderFixture):
    requests = []
    tool_factory = None

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.requests.append(request)
        has_result = request["messages"][-1]["role"] == "tool"
        interview = "[UNCHANGED]" in str(request["messages"][-1].get("content"))
        message = {"role": "assistant", "content": "I published the proposal." if has_result else None}
        if interview:
            message["content"] = "[SOFTENED] I still want access, but a phased plan persuaded me."
            has_result = True
        if not has_result:
            message["tool_calls"] = [{"id": "call_fixture", "type": "function", "function": {
                "name": "create_post", "arguments": json.dumps({"content": "Access requires a concrete plan."})}}]
            if type(self).tool_factory:
                message["tool_calls"] = type(self).tool_factory(request)
        result = {"id": "chat_fixture", "object": "chat.completion", "created": 1,
                  "model": request["model"], "choices": [{"index": 0, "message": message,
                  "finish_reason": "stop" if has_result else "tool_calls"}],
                  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def provider_fixture(handler=ProviderFixture):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class SDKTests(unittest.TestCase):
    def test_real_sdk_structured_parse_full_pipeline(self):
        server, thread = provider_fixture()
        client = OpenAI(api_key="test-fixture-not-a-secret", base_url=f"http://127.0.0.1:{server.server_port}/v1",
                        max_retries=0, timeout=5)
        try:
            model = Model(client, "gpt-4o-mini")
            config = Config(scenario="A library changes its opening hours", agent_count=2, rounds=2)
            agents = prepare(config, model)
            actions = run_round(config, agents, [], model)
            actions += run_round(config, agents, actions, model)
            report = generate_report(config, agents, actions, model)
            self.assertEqual(len(agents), 2)
            self.assertEqual(len(actions), 4)
            self.assertEqual(report.findings[0].action_ids, [1])
            self.assertEqual(model.usage, {"input_tokens": 60, "output_tokens": 30})
            self.assertTrue(all(not req["store"] for req in ProviderFixture.requests))
            schema = ProviderFixture.requests[0]["text"]["format"]["schema"]
            self.assertEqual(schema["properties"]["agents"]["maxItems"], 10)
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_real_sdk_sse_dialogue_and_synthesis(self):
        server, thread = provider_fixture()
        try:
            with OpenAI(api_key='local-fixture',base_url=f'http://127.0.0.1:{server.server_port}/v1',timeout=5,max_retries=0) as client:
                model = Model(client,'gpt-5.4-mini')
                config = Config(scenario='Fictional library extends hours',agent_count=2,rounds=1)
                agents = prepare(config,model)
                events = []
                emit = lambda k,d: events.append((k,d))
                actions = run_round(config,agents,[],model,emit=emit)
                report = generate_report(config,agents,actions,model,emit=emit)
                self.assertEqual(actions[1]['reply_to'],actions[0]['id'])
                deltas = [data['text'] for kind,data in events if kind == 'turn_delta']
                self.assertTrue(any(0 < len(text) < len(actions[0]['text']) for text in deltas))
                self.assertTrue(report.conclusion)
                self.assertTrue(any(k == 'report_delta' for k,d in events))
        finally:
            server.shutdown();server.server_close();thread.join(3)


if __name__ == "__main__":
    unittest.main()
