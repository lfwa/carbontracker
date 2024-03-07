import unittest
from carbontracker.components.handler import Handler

class TestHandler(unittest.TestCase):
    def setUp(self):
        # Create a Handler instance
        self.handler = Handler(pids=[], devices_by_pid={})

    def test_devices_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.handler.devices()

    def test_available_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.handler.available()

    def test_power_usage_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.handler.power_usage()

    def test_init_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.handler.init()

    def test_shutdown_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.handler.shutdown()


if __name__ == '__main__':
    unittest.main()
