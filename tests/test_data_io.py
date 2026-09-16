import json
import tempfile
import unittest
from pathlib import Path

from gtm_selector.data_io import (
    load_wells_csv, save_wells_csv, save_recommendations_csv,
    save_project, load_project,
)
from gtm_selector.sample_data import make_sample_wells
from gtm_selector.params import Settings
from gtm_selector.engine import select_gtm


class DataIoTestCase(unittest.TestCase):
    def test_csv_roundtrip(self):
        wells = make_sample_wells()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wells.csv"
            save_wells_csv(wells, path)
            loaded = load_wells_csv(path)
        self.assertEqual(len(loaded), len(wells))
        self.assertEqual(loaded[0].id, wells[0].id)
        self.assertAlmostEqual(loaded[0].qo, wells[0].qo)
        self.assertEqual(loaded[0].status, wells[0].status)

    def test_recommendations_csv_export(self):
        wells = make_sample_wells()
        settings = Settings()
        recs = select_gtm(wells, settings)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recs.csv"
            save_recommendations_csv(recs, path)
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8-sig")
        self.assertIn("well_id", content)
        self.assertGreater(len(content.splitlines()), 1)

    def test_project_roundtrip(self):
        wells = make_sample_wells()
        settings = Settings()
        settings.economics.oil_price = 40000
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.json"
            save_project(path, wells, settings)
            loaded_wells, loaded_settings = load_project(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(loaded_wells), len(wells))
        self.assertEqual(loaded_settings.economics.oil_price, 40000)
        self.assertIn("wells", raw)
        self.assertIn("settings", raw)


if __name__ == "__main__":
    unittest.main()
