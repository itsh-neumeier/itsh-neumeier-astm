import os
import tempfile
import unittest

from app.generator import render
from app.i18n import translate
from app.monitoring import calls_for_number, parse_named_status, parse_registration_status
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
        self.assertIn("enable=yes", rendered.cdr)
        self.assertIn("loguserfield=yes", rendered.cdr_csv)
        self.assertIn("full => notice,warning,error,debug,verbose,dtmf", rendered.logger)
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
        self.assertEqual(translate("de", "monitoring"), "Monitoring")
        self.assertEqual(translate("en", "call_log"), "Call log")

    def test_monitoring_parsers_detect_provider_status(self):
        registration, detail = parse_registration_status(
            "leonet-out-1-reg/sip:provider.example leonet-out-1-auth Registered",
            "leonet-out-1-reg",
        )
        contact, contact_detail = parse_named_status(
            "Contact:  leonet-out-1-aor/sip:provider.example  abc Avail 12.3",
            "leonet-out-1-aor",
        )

        self.assertEqual(registration, "registered")
        self.assertIn("Registered", detail)
        self.assertEqual(contact, "online")
        self.assertIn("Avail", contact_detail)

    def test_monitoring_call_history_matches_number(self):
        calls = calls_for_number(
            [
                {
                    "src": "491700000000",
                    "dst": "49111111111",
                    "start": "2026-06-03 12:00:00",
                    "duration": "30",
                    "billsec": "20",
                    "disposition": "ANSWERED",
                    "userfield": "inbound:+49111111111",
                },
                {
                    "src": "100",
                    "dst": "4989123456",
                    "start": "2026-06-03 12:05:00",
                    "duration": "10",
                    "billsec": "0",
                    "disposition": "NO ANSWER",
                    "userfield": "outbound:+49111111111->+4989123456",
                },
            ],
            "+49111111111",
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["direction"], "outbound")
        self.assertEqual(calls[1]["direction"], "inbound")


if __name__ == "__main__":
    unittest.main()
