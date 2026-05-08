import json
import pathlib
import tempfile
import unittest

from primal_page.main import create
from primal_page.schemas import SchemeStatus


class TestCreate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.output = pathlib.Path(self._tmpdir.name)

        # Required params
        self.ampliconsize = 400
        self.schemeversion = "v1.0.0"
        self.species = [10]
        self.schemestatus = SchemeStatus.DRAFT
        self.citations = ["test-citation:124"]
        self.authors = ["artic"]
        self.schemename = "test-data-covid"

        # Parsed / optional params
        self.primerbed = pathlib.Path("tests/test_input/test_covid/primer.bed")
        self.reference = pathlib.Path("tests/test_input/test_covid/reference.fasta")
        self.configpath = pathlib.Path("tests/test_input/test_covid/config.json")
        self.algorithmversion = "primalscheme-test"
        self.description = "test-description"
        self.derivedfrom = "test-derivedfrom"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _info_path(self) -> pathlib.Path:
        return (
            self.output
            / self.schemename
            / str(self.ampliconsize)
            / self.schemeversion
            / "info.json"
        )

    def _read_info(self) -> dict:
        return json.loads(self._info_path().read_text())

    def test_create_minimal(self):
        """Test the creation of the scheme, using the config and required params"""
        create(
            output=self.output,
            ampliconsize=self.ampliconsize,
            schemeversion=self.schemeversion,
            species=self.species,
            schemestatus=self.schemestatus,
            citations=self.citations,
            authors=self.authors,
            schemename=self.schemename,
            reference=self.reference,
            primerbed=self.primerbed,
            algorithmversion=self.algorithmversion,
        )

        self.assertTrue(self._info_path().parent.exists())
        self.assertTrue(self._info_path().exists())

        info = self._read_info()
        self.assertEqual(info["schemename"], self.schemename)
        self.assertEqual(info["ampliconsize"], self.ampliconsize)
        self.assertEqual(info["schemeversion"], self.schemeversion)
        self.assertEqual(info["status"], self.schemestatus.value)
        self.assertEqual(info["authors"], self.authors)
        self.assertEqual(info["citations"], self.citations)
        self.assertEqual(info["species"], self.species)
        self.assertEqual(info["algorithmversion"], self.algorithmversion)
        self.assertIsNone(info["description"])
        self.assertIsNone(info["derivedfrom"])

    def test_create_with_algorithmversion(self):
        """Test that algorithmversion is written to info.json when provided"""
        create(
            output=self.output,
            ampliconsize=self.ampliconsize,
            schemeversion=self.schemeversion,
            species=self.species,
            schemestatus=self.schemestatus,
            citations=self.citations,
            authors=self.authors,
            schemename=self.schemename,
            reference=self.reference,
            primerbed=self.primerbed,
            algorithmversion=self.algorithmversion,
        )
        self.assertEqual(self._read_info()["algorithmversion"], self.algorithmversion)

    def test_create_without_algorithmversion(self):
        """Test that algorithmversion defaults to None when omitted"""
        create(
            output=self.output,
            ampliconsize=self.ampliconsize,
            schemeversion=self.schemeversion,
            species=self.species,
            schemestatus=self.schemestatus,
            citations=self.citations,
            authors=self.authors,
            schemename=self.schemename,
            reference=self.reference,
            primerbed=self.primerbed,
        )
        self.assertIsNone(self._read_info()["algorithmversion"])


if __name__ == "__main__":
    unittest.main()
