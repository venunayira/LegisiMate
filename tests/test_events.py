import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from legisimate.server import Manager, Store, make_server
from test_core import FakeModel, FixtureEngine
from legisimate.core import Action
from pydantic import ValidationError


class EventTests(unittest.TestCase):
    def test_invalid_model_json_error_names_type_not_private_output(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'runs.db');model=FakeModel();manager=Manager(store,model,engine=FixtureEngine(model))
            run=manager.create({'scenario':'Change','agent_count':2,'rounds':1});manager.worker.join(3)
            def invalid(*args,**kwargs):
                Action.model_validate_json('{"text":"PRIVATE-SOURCE-NOT-FOR-ERROR')
            model.generate=invalid
            manager.start(run['id']);manager.worker.join(3)
            error=store.get(run['id'])['error']
            self.assertIn('json_invalid',error)
            self.assertNotIn('PRIVATE',error)

    def test_failed_reply_keeps_parent_and_clears_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'runs.db')
            model = FakeModel()
            manager = Manager(store,model,engine=FixtureEngine(model))
            run = manager.create({'scenario':'Change','agent_count':2,'rounds':1})
            manager.worker.join(3)
            original = model.generate
            def fail_reply(output_type,instructions,payload,max_tokens,**kwargs):
                if payload.get('reply_to'):
                    kwargs['on_delta']({'text':'Incomplete reply only'})
                    raise ValueError('invalid generated content')
                return original(output_type,instructions,payload,max_tokens,**kwargs)
            model.generate = fail_reply
            manager.start(run['id']);manager.worker.join(3)
            snapshot = store.view(run['id'])
            self.assertEqual(snapshot['status'],'failed')
            self.assertEqual(snapshot['round'],0)
            self.assertEqual(len(snapshot['actions']),1)
            self.assertEqual(snapshot['drafts'],[])
            self.assertIsNone(snapshot['report'])
            self.assertIn('turn_abort',[e['kind'] for e in store.events(run['id'])])

    def test_view_cursor_recovery_clears_provisional_drafts(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'runs.db')
            model=FakeModel();manager=Manager(store,model,engine=FixtureEngine(model))
            run=manager.create({'scenario':'Change','agent_count':2,'rounds':1});manager.worker.join(3)
            run=store.get(run['id']);run['status']='running';store.save(run)
            stale={'width':10,'height':10,'people':[{'id':1,'x':1,'y':1,'state':'speaking'},{'id':2,'x':2,'y':2,'state':'listening'}],
                   'encounters':[{'id':'old','initiator':1,'partner':2}]}
            store.append_event(run['id'],'room_state',stale)
            meta={'turn_id':'r1-l1-a1','agent_id':1,'lane':1,'round':1,'reply_to':None,'partner_id':2}
            store.append_event(run['id'],'turn_start',meta)
            cursor=store.append_event(run['id'],'turn_delta',{**meta,'text':'Provisional text'})
            view=store.view(run['id'])
            self.assertEqual(view['event_cursor'],cursor)
            self.assertEqual(view['drafts'][0]['text'],'Provisional text')
            store.recover()
            view=store.view(run['id'])
            self.assertEqual(view['drafts'],[])
            self.assertEqual(view['status'],'interrupted')
            self.assertEqual(view['room']['encounters'],[])
            self.assertTrue(all(p['state']=='idle' for p in view['room']['people']))
            self.assertEqual(store.events(run['id'],cursor)[-1]['kind'],'terminal')

    def test_durable_cursor_and_snapshot_events(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'runs.db')
            model = FakeModel()
            manager = Manager(store, model, engine=FixtureEngine(model))
            run = manager.create({'scenario':'Change','agent_count':2,'rounds':1})
            manager.worker.join(3)
            manager.start(run['id'])
            manager.worker.join(3)
            events = store.events(run['id'], 0)
            kinds = [e['kind'] for e in events]
            self.assertIn('turn_delta', kinds)
            self.assertIn('report_delta', kinds)
            self.assertEqual(kinds.count('turn_complete'), 2)
            self.assertEqual(kinds[-1], 'terminal')
            self.assertEqual(store.events(run['id'], events[-2]['id']), [events[-1]])
            self.assertEqual(Store(store.path).events(run['id'], 0), events)
            result = store.get(run['id'])
            reply = result['actions'][1]
            self.assertEqual(reply['reply_to'],result['actions'][0]['id'])
            self.assertLess(kinds.index('turn_delta'),kinds.index('turn_complete'))

    def test_terminal_sse_replay_and_get_never_calls_model(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'runs.db')
            model = FakeModel()
            manager = Manager(store, model, engine=FixtureEngine(model))
            run = manager.create({'scenario':'Change','agent_count':2,'rounds':1})
            manager.worker.join(3)
            manager.start(run['id'])
            manager.worker.join(3)
            calls = len(model.payloads)
            server = make_server(manager,0)
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/api/runs/{run['id']}/events"
                with urllib.request.urlopen(url,timeout=3) as response:
                    self.assertEqual(response.headers['Content-Type'],'text/event-stream')
                    body = response.read().decode()
                    self.assertIn('turn_delta',body)
                    self.assertIn('terminal',body)
                cursor = store.events(run['id'],0)[-2]['id']
                with urllib.request.urlopen(urllib.request.Request(url,headers={'Last-Event-ID':str(cursor)}),timeout=3) as response:
                    body = response.read().decode()
                    self.assertEqual(body.count('event: update'),1)
                    self.assertIn('terminal',body)
                self.assertEqual(len(model.payloads),calls)
            finally:
                server.shutdown(); server.server_close(); thread.join(3)
