"""Check the decision-rule distinction, ties and unusable responses."""
import unittest
from rescore import threshold_record


class ThresholdTests(unittest.TestCase):
    def row(self, probabilities, status='complete'):
        return dict(item_id='toy', told='benign', status=status,
                    probabilities=probabilities, original_letter=max(probabilities, key=probabilities.get))

    def test_highest_a_can_be_below_half(self):
        row = self.row(dict(A=.4, B=.3, C=.2, D=.1))
        self.assertEqual(row['original_letter'], 'A')
        self.assertFalse(threshold_record(row)['detected'])

    def test_exact_half_is_detection(self):
        self.assertTrue(threshold_record(self.row(dict(A=.5, B=.5, C=0, D=0)))['detected'])

    def test_no_rounding_near_threshold(self):
        self.assertFalse(threshold_record(self.row(dict(A=.499999, B=.300001, C=.1, D=.1)))['detected'])

    def test_failure_is_not_a_negative(self):
        with self.assertRaises(ValueError):
            threshold_record(self.row(dict(A=.1, B=.5, C=.2, D=.2), 'failed'))

    def test_invalid_probabilities_are_rejected(self):
        for probabilities in [dict(A=float('nan'), B=.3, C=.2, D=.1),
                              dict(A=.4, B=.3, C=.2), dict(A=.8, B=.3, C=.2, D=.1),
                              dict(A=True, B=0, C=0, D=0)]:
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                threshold_record(self.row(probabilities))


if __name__ == '__main__':
    unittest.main()
