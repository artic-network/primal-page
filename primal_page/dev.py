import hashlib
import json
import pathlib
from typing import Annotated

import typer
from Bio import SeqIO
from primalbedtools.bedfiles import BedFileModifier, BedLineParser

from primal_page.bedfiles import BedfileVersion
from primal_page.logging import log
from primal_page.modify import generate_files, hash_file
from primal_page.schemas import INFO_SCHEMA, Info

app = typer.Typer(no_args_is_help=True)


def reformat_scheme_files(scheme_path: pathlib.Path) -> list[str]:
    """
    Rewrite primer.bed and reference.fasta into their canonical form, in place.

    - primer.bed is sorted and primernames are updated to the current version
    - reference.fasta is re-serialised via SeqIO

    Files are only written if the canonical form differs from what is on disk.

    :param scheme_path: The path to the scheme directory
    :type scheme_path: pathlib.Path
    :return: The names of the files that were rewritten
    :rtype: list[str]
    """
    rewritten: list[str] = []

    # Trim whitespace from primer.bed
    headers, bedlines = BedLineParser().from_file(scheme_path / "primer.bed")
    bedlines = BedFileModifier.sort_bedlines(bedlines)
    bedlines = BedFileModifier.update_primernames(bedlines)

    # If the hash is different, rewrite the file
    bedfile_str = BedLineParser().to_str(headers, bedlines)
    if (
        hash_file(scheme_path / "primer.bed")
        != hashlib.md5(bedfile_str.encode()).hexdigest()
    ):
        log.info(f"Rewriting primer.bed for {scheme_path}")
        BedLineParser().to_file(scheme_path / "primer.bed", headers, bedlines)
        rewritten.append("primer.bed")

    # Hash the reference.fasta file
    # If the hash is different, rewrite the file
    ref_hash = hash_file(scheme_path / "reference.fasta")
    ref_str = "".join(
        x.format("fasta") for x in SeqIO.parse(scheme_path / "reference.fasta", "fasta")
    )
    if ref_hash != hashlib.md5(ref_str.encode()).hexdigest():
        log.info(f"Rewriting reference.fasta for {scheme_path}")
        with open(scheme_path / "reference.fasta", "w") as ref_file:
            ref_file.write(ref_str)
        rewritten.append("reference.fasta")

    return rewritten


@app.command(no_args_is_help=True)
def regenerate(
    schemeinfo: Annotated[
        pathlib.Path,
        typer.Argument(
            help="The path to info.json",
            readable=True,
            exists=True,
            dir_okay=False,
            writable=True,
        ),
    ],
):
    """
    Regenerate the info.json and README.md file for a scheme
        - Rehashes info.json's primer_bed_md5 and reference_fasta_md5
        - Regenerates the README.md file
        - Recalculate the artic-primerbed version
        - Updates the infoschema version to current

    Only info.json and README.md are written. primer.bed and reference.fasta
    are read as-is and never modified. To reformat those files use 'dev reformat'.
    """
    # Check that this is an info.json file (for safety)
    if schemeinfo.name != "info.json":
        raise typer.BadParameter(f"{schemeinfo} is not an info.json file")

    # Get the scheme path
    scheme_path = schemeinfo.parent

    # Get the info
    info_json = json.load(schemeinfo.open())

    info = Info(**info_json)
    info.infoschema = INFO_SCHEMA
    info.articbedversion = BedfileVersion.V3

    # Regenerate the files hashes, from the files as they are on disk
    info.primer_bed_md5 = hash_file(scheme_path / "primer.bed")
    info.reference_fasta_md5 = hash_file(scheme_path / "reference.fasta")

    #####################################
    # Final validation and create files #
    #####################################

    pngs = list(schemeinfo.parent.rglob("*.png"))
    generate_files(info, schemeinfo, pngs)


@app.command(no_args_is_help=True)
def regenerate_all(
    primerschemes: Annotated[
        pathlib.Path,
        typer.Argument(
            help="The parent directory",
            readable=True,
            exists=True,
            writable=True,
            file_okay=False,
        ),
    ],
):
    """
    Rewrites the info.json and README.md of every scheme in the primerschemes
    directory. primer.bed and reference.fasta are not modified.
        Mainly used for migrating to the new info.json schema.
    """
    # Get all the schemes
    info_jsons = list(primerschemes.rglob("info.json"))

    for info_json in info_jsons:
        regenerate(info_json)


@app.command(no_args_is_help=True)
def reformat(
    schemeinfo: Annotated[
        pathlib.Path,
        typer.Argument(
            help="The path to info.json",
            readable=True,
            exists=True,
            dir_okay=False,
            writable=True,
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not prompt before modifying files"),
    ] = False,
):
    """
    THIS MODIFIES primer.bed AND reference.fasta IN PLACE. USE WITH CAUTION
        - Sorts primer.bed and updates the primernames to the current version
        - Re-serialises reference.fasta
        - Then regenerates info.json and README.md
    """
    # Check that this is an info.json file (for safety)
    if schemeinfo.name != "info.json":
        raise typer.BadParameter(f"{schemeinfo} is not an info.json file")

    scheme_path = schemeinfo.parent

    if not yes:
        typer.confirm(
            f"This will rewrite {scheme_path / 'primer.bed'} and "
            f"{scheme_path / 'reference.fasta'} in place. Continue?",
            abort=True,
        )

    rewritten = reformat_scheme_files(scheme_path)
    if rewritten:
        log.info(f"Reformatted {', '.join(rewritten)} for {scheme_path}")
    else:
        log.info(f"No changes needed for {scheme_path}")

    # Update the hashes, info.json and README.md
    regenerate(schemeinfo)


@app.command(no_args_is_help=True)
def reformat_all(
    primerschemes: Annotated[
        pathlib.Path,
        typer.Argument(
            help="The parent directory",
            readable=True,
            exists=True,
            writable=True,
            file_okay=False,
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not prompt before modifying files"),
    ] = False,
):
    """
    THIS MODIFIES THE SCHEMES IN PLACE. USE WITH CAUTION
        Reformats primer.bed and reference.fasta for all schemes in the
        primerschemes directory, then regenerates info.json and README.md.
    """
    # Get all the schemes
    info_jsons = list(primerschemes.rglob("info.json"))

    if not yes:
        typer.confirm(
            f"This will rewrite primer.bed and reference.fasta in place for "
            f"{len(info_jsons)} scheme(s) under {primerschemes}. Continue?",
            abort=True,
        )

    for info_json in info_jsons:
        reformat(info_json, yes=True)
