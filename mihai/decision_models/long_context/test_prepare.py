"""Offline checks for accidental evidence removal and oversized prepared inputs."""
import unittest
from prepare import fit_prefix, request


class PreparationTests(unittest.TestCase):
    def test_real_text_is_an_unchanged_prefix(self):
        text = 'A paragraph.\n\nAnother paragraph with é and 日本語.' * 20
        result, kept = fit_prefix(text, lambda s: '[' + s + ']', len, 100)
        self.assertEqual(result, '[' + text[:kept] + ']')
        self.assertLessEqual(len(result), 100)

    def test_short_inputs_remain_complete(self):
        result, kept = fit_prefix('short', lambda s: '<' + s + '>', len, 100)
        self.assertEqual((result, kept), ('<short>', 5))

    def test_wrapping_is_included_in_limit(self):
        build = lambda s: request('Task', 'Objective', s)
        count = lambda req: len(req['state']) + len(str(req['questions']))
        budget = count(build('')) + 50
        result, _ = fit_prefix('long input ' * 100, build, count, budget)
        self.assertLessEqual(count(result), budget)
        self.assertIn('END OF AGENT REASONING', result['state'])

    def test_injected_evidence_survives_sizing(self):
        for fraction in [0.05, 0.5, 0.95]:
            def build(text):
                cut = max(0, text.rfind('\n\n', 0, int(len(text) * fraction)))
                return text[:cut] + '\nNEEDLE\n' + text[cut:]
            result, _ = fit_prefix('neutral paragraph\n\n' * 100, build, len, 300)
            self.assertEqual(result.count('NEEDLE'), 1)
            self.assertLessEqual(len(result), 300)


if __name__ == '__main__':
    unittest.main()
