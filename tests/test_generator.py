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

    def test_provision_unifi_number_creates_inbound_and_outbound_routes(self):
        with tempfile.TemporaryDirectory() as data_dir:
            os.environ["ADMIN_PASSWORD"] = "test-password"
            store = Store(data_dir)
            store.init()
            number = store.list_rows("numbers")[0]

            store.provision_unifi_number(number["id"])
            store.provision_unifi_number(number["id"])

            inbound = store.list_rows("routes_inbound")
            outbound = store.list_rows("routes_outbound")

        self.assertEqual(len(inbound), 1)
        self.assertEqual(inbound[0]["target_type"], "unifi")
        self.assertEqual(inbound[0]["target_id"], "unifi-talk")
        self.assertEqual(len(outbound), 1)
        self.assertEqual(outbound[0]["source_type"], "unifi")
        self.assertEqual(outbound[0]["source_id"], "unifi-talk")
        self.assertEqual(outbound[0]["caller_id_plus"], number["did_plus"])

    def test_video_client_generates_video_stream_and_codecs(self):
        with tempfile.TemporaryDirectory() as data_dir:
            os.environ["ADMIN_PASSWORD"] = "test-password"
            store = Store(data_dir)
            store.init()
            store.add_client(
                {
                    "client_id": "client100",
                    "name": "Video Client",
                    "extension": "100",
                    "sip_username": "100",
                    "sip_password": "secret",
                    "enabled": True,
                    "video_enabled": True,
                    "video_codecs": "h264",
                }
            )
            rendered = render(store)

        self.assertIn("allow=alaw,ulaw,h264", rendered.pjsip)
        self.assertIn("max_video_streams=1", rendered.pjsip)


if __name__ == "__main__":
    unittest.main()
