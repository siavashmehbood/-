import io,json,unittest
from contextlib import redirect_stdout
from pathlib import Path
from evaluation.language.preflight_cli import main


class PreflightCliTests(unittest.TestCase):
    def test_repo_preflight(self):
        root=Path(__file__).resolve().parents[2]
        out=io.StringIO()
        with redirect_stdout(out): code=main(["--root",str(root)])
        self.assertEqual(code,0)
        payload=json.loads(out.getvalue())
        self.assertTrue(payload["ready"])
        self.assertEqual({x["candidate_id"] for x in payload["eligible"]},{"qwen35-9b","gemma4-12b"})


if __name__=="__main__": unittest.main()
