import unittest
from language_engine.factory import create_language_engine


class RuntimeFactoryTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertIsNone(create_language_engine({}))

    def test_enabled_requires_model(self):
        with self.assertRaises(ValueError):
            create_language_engine({"language_engine":{"enabled":True}})

    def test_enabled_builds_loopback_only_engine(self):
        engine=create_language_engine({"language_engine":{"enabled":True,"model":"candidate"}})
        self.assertEqual(engine.identity["model"],"candidate")
        self.assertEqual(engine.identity["backend"],"local_http")

    def test_remote_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            create_language_engine({"language_engine":{"enabled":True,"model":"candidate",
                "endpoint":"https://remote.example/v1/chat/completions"}})


if __name__=="__main__":
    unittest.main()
