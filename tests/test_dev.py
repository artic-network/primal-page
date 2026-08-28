import json
import pathlib
import tempfile
import unittest

from primalbedtools.bedfiles import BedLineParser, PrimerNameVersion
from typer.testing import CliRunner

from primal_page.main import app, create
from primal_page.modify import hash_file
from primal_page.schemas import SchemeStatus

runner = CliRunner()


class TestDev(unittest.TestCase):
    """
    Tests that 'dev regenerate' never modifies primer.bed/reference.fasta,
    and that 'dev reformat' does.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.output = pathlib.Path(self._tmpdir.name)
        self.schemename = "test-data-covid"
        self.ampliconsize = 400
        self.schemeversion = "v1.0.0"

        create(
            output=self.output,
            ampliconsize=self.ampliconsize,
            schemeversion=self.schemeversion,
            species=[10],
            schemestatus=SchemeStatus.DRAFT,
            citations=["test-citation:124"],
            authors=["artic"],
            schemename=self.schemename,
            reference=pathlib.Path("tests/test_input/test_covid/reference.fasta"),
            primerbed=pathlib.Path("tests/test_input/test_covid/primer.bed"),
            algorithmversion="primalscheme-test",
        )

        self.scheme_path = (
            self.output / self.schemename / str(self.ampliconsize) / self.schemeversion
        )
        self.info_path = self.scheme_path / "info.json"
        self.bed_path = self.scheme_path / "primer.bed"
        self.ref_path = self.scheme_path / "reference.fasta"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _unsort_bedfile(self) -> bytes:
        """Reverse the order of the bedlines, so the file is no longer canonical"""
        lines = self.bed_path.read_text().splitlines(keepends=True)
        headers = [line for line in lines if line.startswith("#")]
        bedlines = [line for line in lines if not line.startswith("#")]
        self.bed_path.write_text("".join(headers + bedlines[::-1]))
        return self.bed_path.read_bytes()

    def _read_info(self) -> dict:
        return json.loads(self.info_path.read_text())

    def test_regenerate_does_not_modify_files(self):
        """dev regenerate must leave primer.bed and reference.fasta byte-identical"""
        bed_bytes = self._unsort_bedfile()
        ref_bytes = self.ref_path.read_bytes()

        result = runner.invoke(app, ["dev", "regenerate", str(self.info_path)])
        assert result.exit_code == 0, result.output

        self.assertEqual(self.bed_path.read_bytes(), bed_bytes)
        self.assertEqual(self.ref_path.read_bytes(), ref_bytes)

    def test_regenerate_updates_hashes(self):
        """dev regenerate rehashes the files as they are on disk"""
        self._unsort_bedfile()

        # The hash in the info.json is now stale
        self.assertNotEqual(
            self._read_info()["primer_bed_md5"], hash_file(self.bed_path)
        )

        result = runner.invoke(app, ["dev", "regenerate", str(self.info_path)])
        assert result.exit_code == 0, result.output

        info = self._read_info()
        self.assertEqual(info["primer_bed_md5"], hash_file(self.bed_path))
        self.assertEqual(info["reference_fasta_md5"], hash_file(self.ref_path))

    def test_reformat_rewrites_bedfile(self):
        """dev reformat --yes sorts the bedfile and updates the hashes"""
        unsorted_bytes = self._unsort_bedfile()

        result = runner.invoke(app, ["dev", "reformat", "--yes", str(self.info_path)])
        assert result.exit_code == 0, result.output

        reformatted_bytes = self.bed_path.read_bytes()
        self.assertNotEqual(reformatted_bytes, unsorted_bytes)

        # All primernames are now in the current version
        _, bedlines = BedLineParser().from_file(self.bed_path)
        for line in bedlines:
            self.assertEqual(line.primername_version, PrimerNameVersion.V2)

        # Reformatting is idempotent
        result = runner.invoke(app, ["dev", "reformat", "--yes", str(self.info_path)])
        assert result.exit_code == 0, result.output
        self.assertEqual(self.bed_path.read_bytes(), reformatted_bytes)

        # And the hashes match the new bytes
        info = self._read_info()
        self.assertEqual(info["primer_bed_md5"], hash_file(self.bed_path))
        self.assertEqual(info["reference_fasta_md5"], hash_file(self.ref_path))

        # The scheme is still valid
        result = runner.invoke(app, ["validate", "scheme", str(self.info_path)])
        assert result.exit_code == 0, result.output

    def test_reformat_aborts_without_confirmation(self):
        """dev reformat prompts, and answering no leaves the files untouched"""
        bed_bytes = self._unsort_bedfile()
        ref_bytes = self.ref_path.read_bytes()
        info_bytes = self.info_path.read_bytes()

        result = runner.invoke(
            app, ["dev", "reformat", str(self.info_path)], input="n\n"
        )
        self.assertNotEqual(result.exit_code, 0)

        self.assertEqual(self.bed_path.read_bytes(), bed_bytes)
        self.assertEqual(self.ref_path.read_bytes(), ref_bytes)
        self.assertEqual(self.info_path.read_bytes(), info_bytes)


class TestDevRegenerateAll(unittest.TestCase):
    """dev regenerate-all must not modify the scheme files either"""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.output = pathlib.Path(self._tmpdir.name)

        create(
            output=self.output,
            ampliconsize=400,
            schemeversion="v1.0.0",
            species=[10],
            schemestatus=SchemeStatus.DRAFT,
            citations=[],
            authors=["artic"],
            schemename="test-data-covid",
            reference=pathlib.Path("tests/test_input/test_covid/reference.fasta"),
            primerbed=pathlib.Path("tests/test_input/test_covid/primer.bed"),
            algorithmversion="primalscheme-test",
        )
        self.scheme_path = self.output / "test-data-covid" / "400" / "v1.0.0"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_regenerate_all_does_not_modify_files(self):
        bed_path = self.scheme_path / "primer.bed"
        ref_path = self.scheme_path / "reference.fasta"

        lines = bed_path.read_text().splitlines(keepends=True)
        bed_path.write_text("".join(lines[::-1]))

        bed_bytes = bed_path.read_bytes()
        ref_bytes = ref_path.read_bytes()

        result = runner.invoke(app, ["dev", "regenerate-all", str(self.output)])
        assert result.exit_code == 0, result.output

        self.assertEqual(bed_path.read_bytes(), bed_bytes)
        self.assertEqual(ref_path.read_bytes(), ref_bytes)


if __name__ == "__main__":
    unittest.main()
