import json
import tempfile
import unittest
from pathlib import Path

from scripts.model_bakeoff import _preserve_unselected_results


class ModelBakeoffArtifactTests(unittest.TestCase):
    def test_selected_run_preserves_other_model_results(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "model_bakeoff.json"
            luna = {"case_id": "one", "model": "gpt-5.6-luna", "raw_output": "keep"}
            old_terra = {"case_id": "one", "model": "gpt-5.6-terra", "raw_output": "replace"}
            output.write_text(
                json.dumps(
                    {
                        "fixture_version": "luna-vs-terra-v1",
                        "results": [luna, old_terra],
                    }
                ),
                encoding="utf-8",
            )

            preserved = _preserve_unselected_results(
                output,
                "luna-vs-terra-v1",
                {"gpt-5.6-terra"},
            )

            self.assertEqual(preserved, [luna])

    def test_selected_run_refuses_cross_fixture_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "model_bakeoff.json"
            output.write_text(
                json.dumps({"fixture_version": "old", "results": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "different fixture version"):
                _preserve_unselected_results(
                    output,
                    "luna-vs-terra-v1",
                    {"gpt-5.6-terra"},
                )


if __name__ == "__main__":
    unittest.main()
