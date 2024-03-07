import unittest
from carbontracker.emissions.conversion.co2eq import convert

class TestConversion(unittest.TestCase):
    def test_convert(self):
        expected = [(2.32558139535, 'km travelled by car')]
        actual = convert(250)
        self.assertAlmostEqual(expected[0][0], actual[0][0], places=5)
        self.assertEqual(expected[0][1], actual[0][1])  # compare unit names

        expected = [(4.6511627907, 'km travelled by car')]
        actual = convert(500)
        self.assertAlmostEqual(expected[0][0], actual[0][0], places=5)
        self.assertEqual(expected[0][1], actual[0][1])

if __name__ == '__main__':
    unittest.main()
