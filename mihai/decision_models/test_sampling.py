"""Offline checks for the sampling policy; no model or dataset is loaded."""
import math
import unittest

from sampling import sampling_distribution, draw_answers


class SamplingTests(unittest.TestCase):
    def test_temperature_matches_softmax_of_scaled_logits(self):
        logits = [2.0, 1.0, 0.0, -1.0]
        normalizer = sum(math.exp(x) for x in logits)
        probabilities = dict(zip("ABCD", [math.exp(x) / normalizer for x in logits]))
        actual = sampling_distribution(probabilities, temperature=0.6, top_p=1)
        expected = [math.exp(x / 0.6) for x in logits]
        for letter, value in zip("ABCD", expected):
            self.assertAlmostEqual(actual[letter], value / sum(expected))

    def test_nucleus_keeps_the_option_crossing_the_cutoff(self):
        actual = sampling_distribution(dict(A=0.6, B=0.25, C=0.1, D=0.05), 1, 0.9)
        self.assertEqual(actual["D"], 0)
        self.assertGreater(actual["C"], 0)
        self.assertAlmostEqual(sum(actual.values()), 1)

    def test_exact_nucleus_boundary(self):
        self.assertEqual(sampling_distribution(dict(A=0.9, B=0.1, C=0, D=0), 1, 0.9),
                         dict(A=1, B=0, C=0, D=0))

    def test_stable_draws_and_distinct_seeds(self):
        distribution = dict(A=0.4, B=0.3, C=0.2, D=0.1)
        first = draw_answers(distribution, "case-one")
        draw_answers(distribution, "another-case")
        self.assertEqual(first, draw_answers(distribution, "case-one"))
        self.assertEqual(len({draw["seed"] for draw in first}), 4)

    def test_excluded_options_never_sampled(self):
        draws = draw_answers(dict(A=0, B=1, C=0, D=0), "one-hot")
        self.assertTrue(all(draw["letter"] == "B" for draw in draws))

    def test_invalid_probabilities_raise(self):
        for invalid in [dict(A=1), dict(A=0.4, B=0.4, C=0.4, D=0.4),
                        dict(A=float("nan"), B=0, C=0, D=0)]:
            with self.assertRaises(ValueError):
                sampling_distribution(invalid)


if __name__ == "__main__":
    unittest.main()
