import hashlib
import pathlib
import tempfile
import unittest

import requests

from primal_page.download import fetch_index, validate_hashes


class TestValidateHashes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.outdir = pathlib.Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_invalid_hash(self):
        """
        Ensures that if the hashes do not match, the file is not written.
        """
        outfile = self.outdir / "no_file_should_write.txt"
        outfile.unlink(missing_ok=True)

        with self.assertRaises(ValueError):
            validate_hashes(
                "test",
                "invalid",
                outfile,
            )

        # Check the file was not written
        ## THIS IS THE MOST IMPORTANT PART OF THE TEST.
        self.assertFalse(outfile.exists())

    def test_valid_hash(self):
        """
        If the hashes match, the file should be written.
        """
        outfile = self.outdir / "should_write.txt"
        outfile.unlink(missing_ok=True)

        text = "test"

        # Create the hash
        expected_hash = hashlib.md5(text.encode()).hexdigest()

        # Run the function
        validate_hashes(text, expected_hash, outfile)

        # Check the file was written
        self.assertTrue(outfile.exists())

        # Check the file contents
        self.assertEqual(outfile.read_text(), text)

        # Remove the file
        outfile.unlink()


class TestFetchIndex(unittest.TestCase):
    def setUp(self) -> None:
        self.index_url = (
            "https://raw.githubusercontent.com/quick-lab/primerschemes/main/index.json"
        )

    def test_fetch_index(self):
        """
        Ensures that the index is fetched correctly.
        """
        from primal_page.download import fetch_index

        index = fetch_index(self.index_url)

        self.assertIsInstance(index, dict)
        self.assertIn("primerschemes", index)

    def test_invalid_url(self):
        """
        Ensures that an invalid URL raises a ValueError.
        """

        with self.assertRaises(requests.exceptions.HTTPError):
            fetch_index(
                "https://raw.githubusercontent.com/quick-lab/primerschemes/main/invalid.json"
            )


if __name__ == "__main__":
    unittest.main()
