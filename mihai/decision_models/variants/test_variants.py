"""Offline checks for the new aggregation and summary boundaries."""
import unittest
from aggregation import aggregate, validate_probabilities
from prompts import summary_request, chunk_request, summarize


def chunk(index, a, status='complete'):
    return {'index': index, 'status': status,
            'probabilities': dict(A=a, B=1-a, C=0, D=0)}


class VariantsTests(unittest.TestCase):
    def test_max_and_mean_answer_different_questions(self):
        result = aggregate([chunk(0, .9), chunk(1, .1), chunk(2, .1)], 3)
        self.assertTrue(result['max']['detected'])
        self.assertFalse(result['mean']['detected'])
        self.assertAlmostEqual(result['mean']['score_a'], 1.1/3)

    def test_threshold_is_not_four_way_argmax(self):
        row = {'index': 0, 'status': 'complete', 'probabilities': dict(A=.4,B=.3,C=.2,D=.1)}
        self.assertEqual(max(row['probabilities'], key=row['probabilities'].get), 'A')
        self.assertFalse(aggregate([row], 1)['max']['detected'])

    def test_failed_chunk_invalidates_both_aggregates(self):
        for result in aggregate([chunk(0,.9),chunk(1,0,'failed')],2).values():
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['detected'])

    def test_no_partial_or_duplicate_aggregation(self):
        for rows, expected in [([],0), ([chunk(0,.5)],2), ([chunk(0,.5),chunk(0,.5)],2)]:
            with self.assertRaises(ValueError): aggregate(rows,expected)

    def test_nan_and_non_normalized_probabilities_rejected(self):
        for p in [dict(A=float('nan'),B=0,C=0,D=0), dict(A=.9,B=.9,C=0,D=0), {'A':1}]:
            with self.assertRaises(ValueError): validate_probabilities(p)

    def test_exact_boundary_and_order_invariance(self):
        a=[chunk(0,.8),chunk(1,.2)]
        self.assertEqual(aggregate(a,2),aggregate(list(reversed(a)),2))
        self.assertTrue(aggregate(a,2)['mean']['detected'])

    def test_summary_input_keeps_order_and_does_not_add_labels(self):
        r=summary_request('task','objective',['first','second'],dict(A='yes',B='no',C='no',D='maybe'))
        self.assertLess(r['state'].index('first'),r['state'].index('second'))
        self.assertNotIn('ground_truth',str(r))
        self.assertIn('not the original transcript',r['questions']['verdict']['instructions'])

    def test_chunk_notice_does_not_mutate_base_request(self):
        r={'state':'evidence','questions':{}}
        result=chunk_request(r,1,3)
        self.assertEqual(r['state'],'evidence')
        self.assertIn('part 2 of 3',result['state'])
        self.assertTrue(result['state'].endswith('evidence'))

    def test_summarizer_gets_evidence_not_grades(self):
        text=summarize('task','objective','{braces} and evidence',0,2,'cot')
        self.assertIn('{braces} and evidence',text)
        self.assertIn('Do not give a verdict',text)


# A small fake storage adapter tests caching without importing the GPU stack.
class CacheTests(unittest.TestCase):
    def test_saved_call_keeps_completed_work_and_checks_identity(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from run_variants import saved_call
        def write(path, result):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(result))
        base=SimpleNamespace(digest=lambda obj:hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest(),
                             read_json=lambda path:json.loads(path.read_text()),write_json=write)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.json'
            first=saved_call(base,path,{'input':'one'},lambda:{'letter':'A'})
            self.assertEqual(first,saved_call(base,path,{'input':'one'},lambda:self.fail('repeated inference')))
            with self.assertRaises(ValueError): saved_call(base,path,{'input':'changed'},lambda:{})

    def test_combined_request_preserves_literal_evidence(self):
        import json
        from types import SimpleNamespace
        from run_variants import request
        base=SimpleNamespace(read_json=lambda path:json.loads(path.read_text()))
        text='Literal AGENT REASONING and the reasoning text from the agent {braces}'
        result=request(base,'all','task','objective',text)
        self.assertIn(text,result['state'])
        self.assertEqual(set(result['questions']['verdict']['criteria']),set('ABCD'))

if __name__ == '__main__':
    unittest.main()
