"""Offline checks for temporal replay and independent RQ2 comparison."""
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from simulate import Simulator, condition, correlate_records, seconds
from evaluate import evaluate_run, temporal_inputs
from export_camunda import pages, normalize
from types import SimpleNamespace


def model(nodes, flows):
    content = "".join(nodes) + "".join(
        f'<sequenceFlow id="f{i}" sourceRef="{a}" targetRef="{b}"/>'
        for i, (a, b) in enumerate(flows)
    )
    return ET.fromstring(f'<process xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" id="p">{content}</process>')


def outcome(action, delay, result=None):
    return {"task_id": action, "job_key": action, "delay_seconds": delay, "result": result or {}}


class ReplayTests(unittest.TestCase):
    def simulate(self, process, records, horizon=20, variables=None):
        return Simulator(process, variables or {}, records, datetime(2026, 1, 1, tzinfo=timezone.utc), horizon).run()

    def test_safe_three_valued_conditions(self):
        self.assertTrue(condition('%x = "normal" and %score > 0.5', {"x": "normal", "score": .8}))
        self.assertFalse(condition('%x = "abnormal" and %missing > 0', {"x": "normal"}))
        self.assertIsNone(condition('%missing > 0 or %x = "abnormal"', {"x": "normal"}))
        with self.assertRaises(ValueError):
            condition('__import__("os")', {})

    def test_declared_null_is_distinct_from_missing_outcome_state(self):
        self.assertFalse(condition('%specialist_result = "bad"', {'specialist_result': None}))
        self.assertTrue(condition('%specialist_result = null', {'specialist_result': None}))
        self.assertIsNone(condition('%specialist_result = "bad"', {}))

    def test_parallel_join_waits_for_both_actions(self):
        process = model(['<startEvent id="s"/>', '<parallelGateway id="split"/>',
                         '<task id="A"/>', '<task id="B"/>', '<parallelGateway id="join"/>',
                         '<task id="C"/>', '<endEvent id="e"/>'],
                        [('s', 'split'), ('split', 'A'), ('split', 'B'), ('A', 'join'),
                         ('B', 'join'), ('join', 'C'), ('C', 'e')])
        report = self.simulate(process, [outcome('A', 2), outcome('B', 5), outcome('C', 1)])
        c = next(e for e in report['events'] if e.get('action') == 'C' and e['type'] == 'action.activated')
        self.assertEqual(c['time'], 5)
        self.assertEqual(set(c['causes']), {'A#1', 'B#1'})
        self.assertTrue(report['completed'])

    def test_default_branch_terminates(self):
        process = ET.fromstring('''<process xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" id="p">
          <startEvent id="s"/><task id="A"/><exclusiveGateway id="g" default="default"/>
          <task id="B"/><endEvent id="e"/>
          <sequenceFlow id="one" sourceRef="s" targetRef="A"/>
          <sequenceFlow id="two" sourceRef="A" targetRef="g"/>
          <sequenceFlow id="yes" sourceRef="g" targetRef="B"><conditionExpression>= x > 10</conditionExpression></sequenceFlow>
          <sequenceFlow id="default" sourceRef="g" targetRef="e"/>
          <sequenceFlow id="last" sourceRef="B" targetRef="e"/>
        </process>''')
        report = self.simulate(process, [outcome('A', 1, {'x': 0})])
        self.assertTrue(report['completed'])
        self.assertFalse(report['unresolved'])
        self.assertEqual([e['action'] for e in report['events'] if e['type'] == 'action.activated'], ['A'])

    def test_boundary_interrupts_and_discards_late_result(self):
        process = model(['<startEvent id="s"/>', '<task id="A"/>', '<task id="B"/>',
                         '<boundaryEvent id="b" attachedToRef="A"><timerEventDefinition><timeDuration>PT3S</timeDuration></timerEventDefinition></boundaryEvent>',
                         '<endEvent id="e"/>'], [('s', 'A'), ('A', 'e'), ('b', 'B'), ('B', 'e')])
        report = self.simulate(process, [outcome('A', 5, {'late': True}), outcome('B', 1)])
        self.assertNotIn('late', report['final_variables'])
        self.assertTrue(any(e['type'] == 'action.cancelled' for e in report['events']))
        self.assertTrue(report['completed'])
        missing = self.simulate(process, [])
        self.assertFalse(any(e['type'] == 'action.cancelled' for e in missing['events']))
        self.assertFalse(any(e.get('action') == 'B' for e in missing['events']))

    def test_recurring_event_scope_and_keep_alive(self):
        process = model(['<startEvent id="s"/>',
                         '<subProcess id="cycle" triggeredByEvent="true"><startEvent id="cs" isInterrupting="false"><timerEventDefinition><timeCycle>R/PT2S</timeCycle></timerEventDefinition></startEvent><task id="A"/><endEvent id="ce"/><sequenceFlow id="c1" sourceRef="cs" targetRef="A"/><sequenceFlow id="c2" sourceRef="A" targetRef="ce"/></subProcess>',
                         '<intermediateCatchEvent id="keep"><timerEventDefinition><timeDuration>PT7S</timeDuration></timerEventDefinition></intermediateCatchEvent>',
                         '<endEvent id="e"><terminateEventDefinition/></endEvent>'], [('s', 'keep'), ('keep', 'e')])
        records = [dict(outcome('A', .5), job_key=str(i)) for i in range(3)]
        report = self.simulate(process, records)
        self.assertEqual([e['time'] for e in report['events'] if e['type'] == 'action.activated'], [2, 4, 6])
        self.assertEqual(report['events'][-1]['type'], 'process.completed')
        self.assertEqual(report['events'][-1]['time'], 7)

    def test_missing_outcome_blocks_only_affected_token(self):
        process = model(['<startEvent id="s"/>', '<parallelGateway id="g"/>', '<task id="A"/>',
                         '<task id="B"/>', '<task id="C"/>', '<endEvent id="e"/>'],
                        [('s', 'g'), ('g', 'A'), ('g', 'B'), ('A', 'C'), ('C', 'e'), ('B', 'e')])
        report = self.simulate(process, [outcome('B', 1)])
        self.assertFalse(report['completed'])
        self.assertEqual(report['unresolved'][0]['action'], 'A')
        self.assertTrue(any(e['type'] == 'action.completed' and e['action'] == 'B' for e in report['events']))

    def test_subprocess_propagates_completion_precedence(self):
        process = model(['<startEvent id="s"/>',
                         '<subProcess id="sub"><startEvent id="ss"/><task id="A"/><endEvent id="se"/><sequenceFlow id="s1" sourceRef="ss" targetRef="A"/><sequenceFlow id="s2" sourceRef="A" targetRef="se"/></subProcess>',
                         '<task id="B"/><endEvent id="e"/>'], [('s', 'sub'), ('sub', 'B'), ('B', 'e')])
        report = self.simulate(process, [outcome('A', 2), outcome('B', 1)])
        b = next(e for e in report['events'] if e.get('action') == 'B' and e['type'] == 'action.activated')
        self.assertEqual(b['causes'], ['A#1'])
        self.assertEqual(b['time'], 2)
        self.assertTrue(any(e['type'] == 'scope.completed' for e in report['events']))

    def test_duration_scale(self):
        self.assertEqual(seconds('PT2S'), 2)
        self.assertEqual(seconds('P1M'), 2592000)

    def test_equal_deadlines_ignore_binary_float_residue(self):
        process = model(['<startEvent id="s"/>', '<endEvent id="e"/>'], [('s', 'e')])
        sim = Simulator(process, {}, [], datetime(2026, 1, 1, tzinfo=timezone.utc), 5000)
        sim.schedule(4034.9945852388087, lambda: None)
        sim.schedule(4034.994585238808, lambda: None)
        self.assertEqual(sim.queue[0][1], 1)

    def test_retries_rejected(self):
        process = model(['<startEvent id="s"/>', '<endEvent id="e"/>'], [('s', 'e')])
        with self.assertRaises(ValueError):
            self.simulate(process, [outcome('A', 1), outcome('A', 2)])


class ComparisonTests(unittest.TestCase):
    def test_shared_temporal_names_do_not_change_input_semantics(self):
        first = temporal_inputs({'TC_A+B_cycle': 'R/PT6S', 'TC_A_execution_duration': 'PT2S'}, 'A')
        second = temporal_inputs({'TC_A_cycle': 'R/PT0.1M', 'TC_A_execution_duration': 'PT2S'}, 'A')
        self.assertEqual(first, second)
        self.assertEqual(first['execution_duration'], 2)

    def fixture(self):
        run = {'id': 'test', 'process': 'P01', 'process_instance_key': '1',
               'started_at': '2026-01-01T00:00:00Z', 'observed_until': '2026-01-01T00:00:10Z'}
        expected = {'run': run, 'horizon_seconds': 10, 'unresolved': [], 'events': [
            {'type': 'action.activated', 'action': 'A', 'occurrence': 1, 'time': 0, 'inputs': {'resource': 'ServiceRequest/A'}, 'causes': []},
            {'type': 'action.completed', 'action': 'A', 'occurrence': 1, 'time': 1},
            {'type': 'process.completed', 'time': 1}]}
        records = [{'task_id': 'A', 'task_instance_key': 'task1', 'process_instance_key': '1', 'job_key': 'j',
                    'invoked_at': run['started_at'], 'result_at': '2026-01-01T00:00:01Z',
                    'inputs': {'resource': 'ServiceRequest/A'}}]
        return expected, records

    def test_no_invented_process_completion_from_worker_logs(self):
        expected, records = self.fixture()
        result = evaluate_run(expected, records, [], 1)
        self.assertEqual(result['metrics']['actions']['tp'], 1)
        self.assertEqual(result['metrics']['termination']['unavailable'], 1)
        expected['run']['observed_status'] = 'ACTIVE'
        result = evaluate_run(expected, records, [], 1)
        self.assertEqual(result['metrics']['termination']['failed'], 1)

    def test_missing_and_additional_actions(self):
        expected, records = self.fixture()
        records[0]['task_id'] = 'B'
        result = evaluate_run(expected, records, [], 1)
        self.assertEqual(result['metrics']['actions']['fp'], 1)
        self.assertEqual(result['metrics']['actions']['fn'], 1)

    def test_engine_correlates_by_activation_not_completion(self):
        expected, records = self.fixture()
        event = {'type': 'action.activated', 'action': 'A', 'process_instance_key': '1',
                 'task_instance_key': 'task1', 'occurrence': 2, 'timestamp': records[0]['invoked_at']}
        correlated = correlate_records(records, [event])
        self.assertEqual(correlated[0]['occurrence'], 2)
        self.assertNotIn('occurrence', records[0])

    def test_active_task_without_result_uses_engine_activation(self):
        expected, _ = self.fixture()
        event = {'type': 'action.activated', 'action': 'A', 'process_instance_key': '1',
                 'task_instance_key': 'task1', 'occurrence': 1, 'timestamp': expected['run']['started_at']}
        result = evaluate_run(expected, [], [event], 1)
        self.assertEqual(result['metrics']['actions']['tp'], 1)
        self.assertEqual(result['metrics']['parameters']['unavailable'], 1)

    def test_expected_iteration_termination_without_process_termination(self):
        expected, records = self.fixture()
        expected['events'] = [e for e in expected['events'] if e['type'] != 'process.completed']
        expected['events'].append({'type': 'scope.completed', 'element': 'iteration', 'occurrence': 1, 'time': 1})
        expected['run'].update(engine_observed_from=expected['run']['started_at'],
                               engine_observed_until=expected['run']['observed_until'])
        result = evaluate_run(expected, records, [], 1)
        self.assertEqual(result['metrics']['scope_completion']['fn'], 1)
        self.assertEqual(result['metrics']['termination']['passed'], 1)

    def test_resolved_historical_incident_is_not_erased(self):
        expected, records = self.fixture()
        event = {'type': 'incident.created', 'process_instance_key': '1',
                 'timestamp': expected['run']['started_at'], 'incident_key': '7',
                 'element': 'gateway', 'error_type': 'CONDITION_ERROR',
                 'error_message': 'No matching condition or default', 'final_state': 'RESOLVED'}
        result = evaluate_run(expected, records, [event], 1)
        self.assertEqual(result['metrics']['incidents']['failed'], 1)
        self.assertEqual(result['metrics']['incidents']['incident_count'], 1)

    def test_internal_pre_worker_cancellation_does_not_prove_timing_failure(self):
        expected, records = self.fixture()
        records[0]['occurrence'] = 2
        engine = [
            {'type': 'action.activated', 'process_instance_key': '1', 'action': 'A',
             'task_instance_key': 'cancelled', 'occurrence': 1, 'timestamp': expected['run']['started_at']},
            {'type': 'action.cancelled', 'process_instance_key': '1', 'action': 'A',
             'occurrence': 1, 'timestamp': expected['run']['started_at']},
        ]
        result = evaluate_run(expected, records, engine, 1)
        self.assertEqual(result['ambiguous_occurrence_actions'], ['A'])
        self.assertEqual(result['metrics']['activation_timing']['failed'], 0)
        self.assertEqual(result['metrics']['activation_timing']['unavailable'], 1)


class ExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_cursor_exhaustion_with_capped_total(self):
        responses = iter([
            {'items': [{'id': '1'}], 'page': {'totalItems': 1, 'hasMoreTotalItems': True, 'endCursor': 'a'}},
            {'items': [{'id': '2'}], 'page': {'totalItems': 1, 'hasMoreTotalItems': True, 'endCursor': 'b'}},
            {'items': [], 'page': {'totalItems': 1, 'hasMoreTotalItems': True, 'endCursor': None}},
        ])

        async def search(page):
            response = next(responses)
            return SimpleNamespace(to_dict=lambda: response)

        result = await pages(search, 'id')
        self.assertEqual([r['id'] for r in result], ['1', '2'])

    def test_export_correlates_overlap_by_start_not_finish(self):
        first = {'processInstanceKey': '1', 'elementId': 'A1', 'type': 'SERVICE_TASK',
                 'elementInstanceKey': '11', 'startDate': '2026-01-01T00:00:00Z',
                 'endDate': '2026-01-01T00:00:05Z', 'state': 'COMPLETED'}
        second = {**first, 'elementInstanceKey': '12', 'startDate': '2026-01-01T00:00:01Z',
                  'endDate': '2026-01-01T00:00:02Z'}
        events = normalize([second, first], {'A1'})
        activations = [e for e in events if e['type'] == 'action.activated']
        self.assertEqual([(e['task_instance_key'], e['occurrence']) for e in activations], [('11', 1), ('12', 2)])


if __name__ == '__main__':
    unittest.main()
