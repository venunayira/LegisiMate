import copy
import threading
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, patch

from legisimate.core import Action, Config, Model, run_round
from test_core import FakeModel, roster


class ConversationTests(unittest.TestCase):
    def test_failed_task_before_coordinator_wait_is_not_swallowed(self):
        class ImmediatePool:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def submit(self,fn,*args):
                future=Future()
                try:future.set_result(fn(*args))
                except Exception as exc:future.set_exception(exc)
                return future
        fake=FakeModel();original=fake.generate;calls=[]
        def fail_other(*args,**kwargs):
            calls.append(1)
            if len(calls)>2:raise ValueError('Provider failed')
            return original(*args,**kwargs)
        fake.generate=fail_other
        def collect_success_first(futures,**kwargs):
            succeeded={f for f in futures if f.exception() is None}
            return succeeded,set(futures)-succeeded
        with patch('legisimate.core.ThreadPoolExecutor',ImmediatePool),patch('legisimate.core.wait',collect_success_first),self.assertRaises(ValueError):
            run_round(Config(scenario='Change',agent_count=4),roster(4),[],fake)

    def test_cancel_while_entering_commit_lock_cannot_publish_turn(self):
        stopped=threading.Event();committed=[]
        class CancelOnAcquire:
            def __enter__(self):stopped.set()
            def __exit__(self,*args):return False
        with patch('legisimate.core.Lock',return_value=CancelOnAcquire()):
            result=run_round(Config(scenario='Change',agent_count=1),roster(1),[],FakeModel(),
                             cancelled=stopped.is_set,on_action=committed.append)
        self.assertEqual(result,[])
        self.assertEqual(committed,[])

    def test_parallel_openings_and_sequential_exact_parent_replies(self):
        opened, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        starts = []
        fake = FakeModel()
        def decide(output_type, instructions, payload, max_tokens, **kwargs):
            if payload['reply_to'] is None:
                with lock:
                    starts.append(payload['persona']['id'])
                    if len(starts) == 2:
                        opened.set()
                release.wait(3)
                return Action(kind='post', text=f"Argument from {payload['persona']['name']}", stance='oppose', reply_to=None)
            parent = payload['feed'][-1]
            self.assertEqual(parent['id'], payload['reply_to'])
            self.assertNotEqual(parent['agent_id'], payload['persona']['id'])
            self.assertEqual(len(payload['feed']), 1)
            return Action(kind='reply', text=f"I disagree with {parent['text']}", stance='support', reply_to=parent['id'])
        fake.generate = decide
        result = []
        worker = threading.Thread(target=lambda: result.extend(run_round(
            Config(scenario='Change', agent_count=4), roster(4), [], fake)))
        worker.start()
        try:
            self.assertTrue(opened.wait(2))
        finally:
            release.set()
            worker.join(3)
        self.assertEqual(len(result), 4)
        self.assertEqual(sorted(a['agent_id'] for a in result), [1,2,3,4])
        for reply in [a for a in result if a['kind'] == 'reply']:
            parent = next(a for a in result if a['id'] == reply['reply_to'])
            self.assertLess(parent['id'], reply['id'])
            self.assertEqual(parent['lane'], reply['lane'])

    def test_turn_deltas_arrive_before_finalized_evidence(self):
        events, committed = [], []
        fake = FakeModel()
        def decide(output_type, instructions, payload, max_tokens, on_delta=None, **kwargs):
            on_delta({'text':'I disagree'})
            self.assertFalse(any(e['agent_id'] == payload['persona']['id'] for e in committed))
            return Action(kind='reply' if payload['reply_to'] else 'post', text='I disagree with the cost.',
                          stance='oppose', reply_to=payload['reply_to'])
        fake.generate = decide
        result = run_round(Config(scenario='Change', agent_count=2), roster(), [], fake,
                           emit=lambda kind,data: events.append((kind,copy.deepcopy(data))), on_action=committed.append)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(committed), 2)
        self.assertTrue(any(kind == 'turn_delta' and data['text'] == 'I disagree' for kind,data in events))
        self.assertEqual([kind for kind,_ in events].count('turn_start'), 2)

    def test_invalid_or_cancelled_turn_is_not_committed(self):
        fake = FakeModel()
        events, committed = [], []
        def invalid(output_type, instructions, payload, max_tokens, on_delta=None, **kwargs):
            if on_delta: on_delta({'text':'Draft only'})
            return Action(kind='reply', text='Invalid self reply', stance='neutral', reply_to=99)
        fake.generate = invalid
        with self.assertRaises(ValueError):
            run_round(Config(scenario='Change', agent_count=2), roster(), [], fake,
                      emit=lambda k,d: events.append(k), on_action=committed.append)
        self.assertEqual(committed, [])
        self.assertIn('turn_abort', events)
        self.assertEqual(run_round(Config(scenario='Change', agent_count=2), roster(), [], fake,
                                   cancelled=lambda:True), [])

    def test_cancel_after_parent_never_launches_dependent_reply(self):
        fake = FakeModel()
        stopped = threading.Event()
        committed = []
        def commit(action):
            committed.append(action)
            stopped.set()
        result = run_round(Config(scenario='Change',agent_count=2),roster(),[],fake,
                           cancelled=stopped.is_set,on_action=commit)
        self.assertEqual(len(fake.payloads),1)
        self.assertEqual(result,committed)
        self.assertEqual(len(committed),1)

    def test_one_and_odd_agent_rounds_never_add_extra_people(self):
        for count in [1,3,5,9,10]:
            with self.subTest(count=count):
                result = run_round(Config(scenario='Change',agent_count=count),roster(count),[],FakeModel())
                self.assertEqual(sorted(a['agent_id'] for a in result),list(range(1,count+1)))
                self.assertEqual(len({a['id'] for a in result}),count)

    def test_sdk_stream_emits_decoded_text_and_closes_on_cancel(self):
        client = Mock()
        stream = Mock()
        stream.__enter__ = Mock(return_value=stream)
        stream.__exit__ = Mock(return_value=False)
        raw = '{"kind":"post","text":"Hello \\u263a", "stance":"neutral","reply_to":null}'
        chunks = [raw[:28], raw[28:35], raw[35:]]
        stream.__iter__ = Mock(return_value=iter([SimpleNamespace(type='response.output_text.delta', delta=s) for s in chunks]))
        stream.get_final_response.return_value = SimpleNamespace(status='completed',
            output_parsed=Action(kind='post', text='Hello ☺', stance='neutral', reply_to=None), usage=None)
        client.responses.stream.return_value = stream
        deltas = []
        result = Model(client,'gpt-5.4-mini').generate(Action,'Test',{},700,on_delta=deltas.append)
        self.assertEqual(result.text, 'Hello ☺')
        self.assertEqual(deltas[-1]['text'], 'Hello ☺')
        self.assertTrue(all('kind' not in d for d in deltas))
        stream.__exit__.assert_called_once()
        self.assertFalse(client.responses.stream.call_args.kwargs['store'])
        stream.reset_mock()
        stream.__iter__ = Mock(return_value=iter([SimpleNamespace(type='response.output_text.delta',delta=raw)]))
        checks = iter([False, True])
        with self.assertRaises(ValueError):
            Model(client,'gpt-5.4-mini').generate(Action,'Test',{},700,on_delta=deltas.append,cancelled=lambda:next(checks))
        stream.__exit__.assert_called_once()
