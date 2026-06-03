import os
import tempfile
import unittest

from app.generator import render
from app.i18n import translate
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

    def test_rows_are_updateable(self):
        with tempfile.TemporaryDirectory() as data_dir:
            os.environ["ADMIN_PASSWORD"] = "test-password"
            store = Store(data_dir)
            store.init()
            number = store.list_rows("numbers")[0]

            store.update_number(number["id"], "+49111111111", "user1", "pass1")
            store.add_client(
                {
                    "client_id": "client100",
                    "name": "Client",
                    "extension": "100",
                    "sip_username": "100",
                    "sip_password": "secret",
                    "enabled": True,
                }
            )
            client = store.list_rows("clients")[0]
            store.update_client(
                client["id"],
                {
                    "client_id": "client101",
                    "name": "Client 101",
                    "extension": "101",
                    "sip_username": "101",
                    "sip_password": "secret2",
                    "enabled": True,
                    "ip_acl": "192.168.10.50/32",
                    "caller_id_plus": "+49111111111",
                    "client_type": "video-phone",
                    "audio_codecs": "alaw,ulaw",
                    "video_enabled": True,
                    "video_codecs": "h264",
                },
            )

            updated_number = store.list_rows("numbers")[0]
            updated_client = store.list_rows("clients")[0]

        self.assertEqual(updated_number["did_plus"], "+49111111111")
        self.assertEqual(updated_client["client_id"], "client101")
        self.assertEqual(updated_client["ip_acl"], "192.168.10.50/32")
        self.assertEqual(updated_client["video_codecs"], "h264")

    def test_routes_are_updateable(self):
        with tempfile.TemporaryDirectory() as data_dir:
            os.environ["ADMIN_PASSWORD"] = "test-password"
            store = Store(data_dir)
            store.init()
            number = store.list_rows("numbers")[0]
            store.add_inbound_route(
                {
                    "did_plus": number["did_plus"],
                    "target_type": "unifi",
                    "target_id": "unifi-talk",
                    "ring_seconds": 45,
                    "description": "old",
                }
            )
            store.add_outbound_route(
                {
                    "source_type": "unifi",
                    "source_id": "unifi-talk",
                    "number_id": number["id"],
                    "caller_id_plus": number["did_plus"],
                    "description": "old",
                }
            )

            inbound = store.list_rows("routes_inbound")[0]
            outbound = store.list_rows("routes_outbound")[0]
            store.update_inbound_route(
                inbound["id"],
                {
                    "did_plus": "+49222222222",
                    "target_type": "client",
                    "target_id": "client101",
                    "ring_seconds": 30,
                    "description": "new inbound",
                },
            )
            store.update_outbound_route(
                outbound["id"],
                {
                    "source_type": "client",
                    "source_id": "client101",
                    "number_id": number["id"],
                    "caller_id_plus": "+49222222222",
                    "description": "new outbound",
                },
            )

            updated_inbound = store.list_rows("routes_inbound")[0]
            updated_outbound = store.list_rows("routes_outbound")[0]

        self.assertEqual(updated_inbound["target_type"], "client")
        self.assertEqual(updated_inbound["ring_seconds"], 30)
        self.assertEqual(updated_outbound["source_type"], "client")
        self.assertEqual(updated_outbound["caller_id_plus"], "+49222222222")

    def test_translations_support_german_and_english(self):
        self.assertEqual(translate("de", "save"), "Speichern")
        self.assertEqual(translate("en", "save"), "Save")


if __name__ == "__main__":
    unittest.main()
