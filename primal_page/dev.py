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

    Ensures work/config.json has no absolute paths
        - Ensures hashes in config.json are removed
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

    # get scheme id
    scheme_id = f"{info.schemename}/{info.ampliconsize}/{info.schemeversion}"

    # Trim whitespace from primer.bed and reference.fasta
    headers, bedlines = BedLineParser().from_file(scheme_path / "primer.bed")
    bedlines = BedFileModifier.sort_bedlines(bedlines)
    bedlines = BedFileModifier.update_primernames(bedlines)

    # If the hash is different, rewrite the file
    bedfile_str = BedLineParser().to_str(headers, bedlines)
    if (
        hash_file(scheme_path / "primer.bed")
        != hashlib.md5(bedfile_str.encode()).hexdigest()
    ):
        log.info(f"Regenerating primer.bed for {scheme_id}")
        BedLineParser().to_file(scheme_path / "primer.bed", headers, bedlines)

    # Hash the reference.fasta file
    # If the hash is different, rewrite the file
    ref_hash = hash_file(scheme_path / "reference.fasta")
    ref_str = "".join(
        x.format("fasta") for x in SeqIO.parse(scheme_path / "reference.fasta", "fasta")
    )
    if ref_hash != hashlib.md5(ref_str.encode()).hexdigest():
        log.info(f"Regenerating reference.fasta for {scheme_id}")
        with open(scheme_path / "reference.fasta", "w") as ref_file:
            ref_file.write(ref_str)

    # if articbedversion not set then set it
    articbedversion = BedfileVersion.V3
    if articbedversion == BedfileVersion.INVALID:
        raise typer.BadParameter(
            f"Could not determine artic-primerbed version for {scheme_path / 'primer.bed'}"
        )
    info.articbedversion = articbedversion

    # Regenerate the files hashes
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
    THIS MODIFIES THE SCHEMES IN PLACE. USE WITH CAUTION
        Regenerates all schemes in the primerschemes directory.
        Mainly used for migrating to the new info.json schema.
    """
    # Get all the schemes
    info_jsons = list(primerschemes.rglob("info.json"))

    for info_json in info_jsons:
        regenerate(info_json)
