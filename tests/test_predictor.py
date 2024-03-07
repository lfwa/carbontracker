import unittest
import numpy as np
from carbontracker import predictor

class TestPredictor(unittest.TestCase):
    def test_predict_energy(self):
        total_epochs = 10
        epoch_energy_usages = np.array([10, 20, 30, 40, 50])
        expected_result = total_epochs * np.mean(epoch_energy_usages)
        result = predictor.predict_energy(total_epochs, epoch_energy_usages)
        self.assertEqual(result, expected_result)

    def test_predict_time(self):
        total_epochs = 10
        epoch_times = np.array([1, 2, 3, 4, 5])
        expected_result = total_epochs * np.mean(epoch_times)
        result = predictor.predict_time(total_epochs, epoch_times)
        self.assertEqual(result, expected_result)

