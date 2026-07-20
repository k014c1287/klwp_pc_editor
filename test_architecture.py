import unittest

from tools.check_object_calisthenics import inspect_package


class ArchitectureTests(unittest.TestCase):
    def test_object_calisthenics_rules(self):
        violations = inspect_package("klwp") + inspect_package("tools")
        messages = [violation.display() for violation in violations]
        self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
