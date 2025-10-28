import unittest
from main import read_config


class TestLoadFunctions(unittest.TestCase):
    def test_load_tasks(self):
        result = read_config("config.yaml.sample")
        self.assertIsInstance(result, dict)
