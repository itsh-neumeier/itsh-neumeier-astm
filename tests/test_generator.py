import os
import tempfile
import unittest

from app.generator import render
from app.store import Store


class GeneratorTest(unittest.TestCase):
    def test_default_config_contains_core_sections(self):
        with tempfile.TemporaryDirectory() as data_dir:
            os.environ["ADMIN_PASSWORD"] = "test-password"
            store = Store(data_dir)
            store.init()
            rendered = render(store)

        self.assertIn("[transport-udp]", rendered.pjsip)
        self.assertIn("[unifi-talk]", rendered.pjsip)
        self.assertIn("[leonet-out-1]", rendered.pjsip)
        self.assertIn("[from-unifi]", rendered.extensions)
        self.assertIn("IP Address Range", rendered.unifi_summary)


if __name__ == "__main__":
    unittest.main()
