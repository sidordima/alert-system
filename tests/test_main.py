import unittest
from main import load_tasks, read_config


class TestLoadFunctions(unittest.TestCase):
    def test_load_tasks(self):
        result = read_config("config.yaml.sample")
        self.assertIsInstance(result, dict)
