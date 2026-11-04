import unittest
from unittest.mock import patch
import tempfile
import shutil
from pathlib import Path
import asyncio

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from file_handler import (
    FileHandler,
    normalize_acceptance_stem,
    CRADLE_HASH_PATTERN,
)



class TestLucidEmissionLookup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.download_dir = Path(self.test_dir) / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.mock_lucid = Path(self.test_dir) / "lucid_mount"
        self.mock_lucid.mkdir(parents=True, exist_ok=True)
        self.handler = FileHandler(
            download_base_path=str(self.download_dir),
            lucid_bases_config={"Electrolux": self.mock_lucid}
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_normalize_acceptance_stem_cradle_hash(self):
        # 1. Exact 1147007 case
        orig, cleaned = normalize_acceptance_stem("ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4")
        self.assertEqual(orig, "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O")
        self.assertEqual(cleaned, "ELUX_CH_Care_Hero1_11s_1x1_FR")

    def test_normalize_acceptance_stem_no_hash(self):
        # 2. No suffix or standard words
        orig, cleaned = normalize_acceptance_stem("ELUX_CH_Care_Hero1_11s_1x1_FR.mov")
        self.assertEqual(orig, "ELUX_CH_Care_Hero1_11s_1x1_FR")
        self.assertEqual(cleaned, "ELUX_CH_Care_Hero1_11s_1x1_FR")

    def test_normalize_acceptance_stem_not_matching_hash_policy(self):
        # 3. Last segment is not exactly 7 alphanumeric chars
        orig, cleaned = normalize_acceptance_stem("video_version_123456.mp4")
        self.assertEqual(cleaned, "video_version_123456")

        orig, cleaned = normalize_acceptance_stem("video_version_12345678.mp4")
        self.assertEqual(cleaned, "video_version_12345678")

        orig, cleaned = normalize_acceptance_stem("video_version_special-1.mp4")
        self.assertEqual(cleaned, "video_version_special-1")

    def test_exact_1147007_case_fallback_resolution(self):
        # Setup campaign folder
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml_french = campaign_folder / "EML" / "French (CH)" / "MOV"
        eml_french.mkdir(parents=True, exist_ok=True)

        target_emission = eml_french / "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov"
        target_emission.write_bytes(b"mock video data")

        cradle_id = "1147007"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",  # Generic template ID
            "langCode": "FR",
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        # Run with patched mounted bases pointing to our temp dir
        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertTrue(result["success"])
        self.assertEqual(result["filename"], "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov")
        copied_file = cradle_folder / "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov"
        self.assertTrue(copied_file.exists())

    def test_correct_template_id_takes_precedence(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml = campaign_folder / "EML"
        eml.mkdir(parents=True, exist_ok=True)

        # File matching explicit template ID
        template_file = eml / "UniqueAsset_TID999_FR.mov"
        template_file.write_bytes(b"template file")

        # Fallback candidate matching acceptance stem
        fallback_file = eml / "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov"
        fallback_file.write_bytes(b"fallback file")

        cradle_id = "1147008"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "TID999",  # Valid specific template ID
            "langCode": "FR",
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertTrue(result["success"])
        self.assertEqual(result["filename"], "UniqueAsset_TID999_FR.mov")

    def test_ambiguous_candidates_returns_error(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml = campaign_folder / "EML"
        eml.mkdir(parents=True, exist_ok=True)

        # Two candidates in EML with identical format and size
        cand1 = eml / "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov"
        cand2 = eml / "ELUX_CH_Care_Hero1_11s_1x1_FR_TikTok.mov"
        cand1.write_bytes(b"12345")
        cand2.write_bytes(b"12345")

        cradle_id = "1147009"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",
            "langCode": "FR",
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertFalse(result["success"])
        self.assertIn("AMBIGUOUS_LUCID_EMISSION_MATCH", result["error"])
        self.assertIn("ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov", result["error"])
        self.assertIn("ELUX_CH_Care_Hero1_11s_1x1_FR_TikTok.mov", result["error"])

    def test_ambiguous_one_in_eml_one_outside_eml_returns_ambiguous(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml = campaign_folder / "EML"
        eml.mkdir(parents=True, exist_ok=True)
        preview = campaign_folder / "preview"
        preview.mkdir(parents=True, exist_ok=True)

        cand_eml = eml / "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov"
        cand_outside = preview / "ELUX_CH_Care_Hero1_11s_1x1_FR_Preview.mov"
        cand_eml.write_bytes(b"99999999")
        cand_outside.write_bytes(b"11111111")

        cradle_id = "1147012"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",
            "langCode": "FR",
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertFalse(result["success"])
        self.assertIn("AMBIGUOUS_LUCID_EMISSION_MATCH", result["error"])
        self.assertIn("ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov", result["error"])
        self.assertIn("ELUX_CH_Care_Hero1_11s_1x1_FR_Preview.mov", result["error"])

    def test_candidate_without_target_language_confirmation_rejected(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml_neutral = campaign_folder / "EML" / "Neutral"
        eml_neutral.mkdir(parents=True, exist_ok=True)

        # Candidate matches stem but has NO language confirmation in name or folder path
        cand = eml_neutral / "ELUX_CH_Care_Hero1_11s_1x1.mov"
        cand.write_bytes(b"12345")

        cradle_id = "1147013"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",
            "langCode": "FR",  # Requires FR confirmation
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertFalse(result["success"])
        self.assertIn("No video file found", result["error"])

    def test_candidate_fr_in_french_folder_is_selected(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        french_folder = campaign_folder / "EML" / "French (CH)" / "MOV"
        french_folder.mkdir(parents=True, exist_ok=True)

        cand = french_folder / "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov"
        cand.write_bytes(b"12345")

        cradle_id = "1147014"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",
            "langCode": "FR",
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertTrue(result["success"])
        self.assertEqual(result["filename"], "ELUX_CH_Care_Hero1_11s_1x1_FR_Meta.mov")

    def test_no_candidates_returns_failure(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml = campaign_folder / "EML"
        eml.mkdir(parents=True, exist_ok=True)

        # Completely unrelated file
        cand = eml / "Completely_Different_Asset.mov"
        cand.write_bytes(b"12345")

        cradle_id = "1147010"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",
            "langCode": "FR",
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertFalse(result["success"])
        self.assertIn("No video file found", result["error"])

    def test_language_mismatch_rejected(self):
        campaign_folder = self.mock_lucid / "26_05657 Swiss Marco Odermatt Campaign Vol. 2"
        eml_german = campaign_folder / "EML" / "German (CH)"
        eml_german.mkdir(parents=True, exist_ok=True)

        # German file matching the stem except language
        cand = eml_german / "ELUX_CH_Care_Hero1_11s_1x1_DE_Meta.mov"
        cand.write_bytes(b"12345")

        cradle_id = "1147011"
        cradle_folder = self.download_dir / cradle_id
        cradle_folder.mkdir(parents=True, exist_ok=True)

        file_info = {
            "jobNumber": "26|05657",
            "templateId": "master1111",
            "langCode": "FR",  # Requesting French!
            "clientName": "Electrolux",
            "acceptanceName": "ELUX_CH_Care_Hero1_11s_1x1_FR_OTVOY5O.mp4",
        }

        async def run_test():
            return await self.handler.handle_lucid_emission_file(file_info, cradle_folder, cradle_id)

        result = asyncio.run(run_test())
        self.assertFalse(result["success"])
        self.assertIn("No video file found", result["error"])


if __name__ == "__main__":
    unittest.main()
