import unittest
from language_engine.candidates import CandidateManifest


class CandidateManifestTests(unittest.TestCase):
    def test_manifest_requires_pinned_revision_and_license(self):
        with self.assertRaises(ValueError):
            CandidateManifest("qwen","qwen","model","","").validate()

    def test_remote_only_candidate_is_ineligible(self):
        with self.assertRaises(ValueError):
            CandidateManifest("x","x","x","sha","license",local_capable=False).validate()

    def test_valid_manifest_is_backend_neutral(self):
        item=CandidateManifest("candidate-a","family-a","org/model","revision","license",
                               quantization="q4",context_length=32768).validate()
        self.assertEqual(item.quantization,"q4")


if __name__=="__main__":
    unittest.main()
