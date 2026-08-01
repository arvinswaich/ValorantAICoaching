import hashlib
import unittest

from updater import (
    find_windows_asset,
    handle_update_arguments,
    is_newer_version,
    parse_version,
    verify_digest,
)


class UpdaterTests(unittest.TestCase):
    def test_parse_version_accepts_release_tags(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.4"), (1, 4, 0))
        self.assertEqual(parse_version("v2.0.0-beta"), (2, 0, 0))

    def test_only_newer_versions_are_updates(self):
        self.assertTrue(is_newer_version("v1.0.2", current="1.0.1"))
        self.assertFalse(is_newer_version("v1.0.1", current="1.0.1"))
        self.assertFalse(is_newer_version("v1.0.0", current="1.0.1"))

    def test_find_windows_asset_uses_expected_filename(self):
        release = {
            "assets": [
                {"name": "source.zip"},
                {"name": "ValorantVODCoach.exe", "size": 123},
            ]
        }
        self.assertEqual(find_windows_asset(release)["size"], 123)

    def test_sha256_digest_is_verified(self):
        actual = hashlib.sha256(b"trusted update").hexdigest()
        verify_digest(actual, f"sha256:{actual}")
        with self.assertRaisesRegex(RuntimeError, "integrity"):
            verify_digest(actual, "sha256:" + "0" * 64)

    def test_normal_startup_has_no_update_arguments(self):
        self.assertFalse(handle_update_arguments([]))


if __name__ == "__main__":
    unittest.main()
