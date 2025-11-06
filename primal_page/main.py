import json
import pathlib
import shutil
from importlib.metadata import version
from typing import Annotated, Optional

import typer
from Bio import Seq, SeqIO, SeqRecord
from primalbedtools.bedfiles import BedFileModifier, BedLineParser, PrimerNameVersion

from primal_page.aliases import app as aliases_app
from primal_page.bedfiles import BedfileVersion
from primal_page.build_index import create_index
from primal_page.dev import app as dev_app
from primal_page.download import app as download_app
from primal_page.errors import InvalidReference, SchemeExists
from primal_page.logging import log
from primal_page.modify import app as modify_app
from primal_page.modify import generate_files, hash_file
from primal_page.schemas import (
    Collection,
    Info,
    IUPACAmbiguousDNA,
    Links,
    PrimerClass,
    SchemeStatus,
)
from primal_page.validate import app as validate_app
from primal_page.validate import validate_bedfile, validate_ref_select_file

# Create the typer app
app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
app.add_typer(
    modify_app,
    name="modify",
    help="Modify an existing scheme's metadata (info.json)",
)
app.add_typer(
    download_app,
    name="download",
    help="Download schemes from the index.json",
)
app.add_typer(dev_app, name="dev", help="Development commands", hidden=True)
app.add_typer(aliases_app, name="aliases", help="Manage aliases")
app.add_typer(validate_app, name="validate", help="Validate a scheme")


def typer_callback_version(value: bool):
    if value:
        typer.echo(f"primal-page version: {version('primal-page')}")
        raise typer.Exit()


@app.callback()
def primal_page(
    value: Annotated[bool, typer.Option] = typer.Option(
        False, "--version", callback=typer_callback_version
    ),
):
    pass


def validate_ref_records(ref_records: list[SeqRecord.SeqRecord]):
    """
    Validate the reference.fasta file
    :param ref_file: The path to the reference.fasta file
    :raises InvalidReference: If the reference.fasta file is invalid
    """

    for record in ref_records:
        assert isinstance(record.seq, Seq.Seq)
        # Check DNA sequence
        seq_bases = set(record.seq)
        if not seq_bases.issubset(IUPACAmbiguousDNA):
            raise InvalidReference(
                f"Invalid DNA bases ({', '.join(seq_bases.difference(IUPACAmbiguousDNA))}) found in {record.id}"
            )
        if len(record.seq) == 0:
            raise InvalidReference(f"Empty sequence found in {record.id}")


@app.command(no_args_is_help=True)
def create(
    schemename: Annotated[
        str,
        typer.Option(help="The name of the scheme"),
    ],
    ampliconsize: Annotated[
        int,
        typer.Option(help="Amplicon size", min=100),
    ],
    schemeversion: Annotated[
        str,
        typer.Option(
            help="Scheme version, default is parsed from config.json",
        ),
    ],
    species: Annotated[
        list[int],
        typer.Option(
            help="The species this scheme targets. Please use NCBI taxonomy ids"
        ),
    ],
    authors: Annotated[
        list[str],
        typer.Option(
            help="Any authors. To provide multiple, use --authors '1' --authors '2'"
        ),
    ],
    primerbed: Annotated[
        pathlib.Path,
        typer.Option(
            help="The path to the primer.bed file",
            readable=True,
        ),
    ],
    reference: Annotated[
        pathlib.Path,
        typer.Option(
            help="The path to the reference.fasta file",
            readable=True,
        ),
    ],
    schemestatus: Annotated[
        SchemeStatus, typer.Option(help="Scheme status")
    ] = SchemeStatus.DRAFT.value,  # type: ignore
    citations: Annotated[
        list[str], typer.Option(help="Any associated citations. Please use DOI")
    ] = [],
    output: Annotated[
        pathlib.Path,
        typer.Option(help="Where to output the scheme", writable=True),
    ] = pathlib.Path("primerschemes"),
    configpath: Annotated[
        Optional[pathlib.Path],
        typer.Option(
            help="Where the config.json file is located", readable=True, exists=True
        ),
    ] = None,
    algorithmversion: Annotated[
        Optional[str], typer.Option(help="The version of primalscheme or other")
    ] = None,
    description: Annotated[
        Optional[str], typer.Option(help="A description of the scheme")
    ] = None,
    derivedfrom: Annotated[
        Optional[str],
        typer.Option(help="Which scheme has this scheme been derived from"),
    ] = None,
    primerclass: Annotated[
        PrimerClass, typer.Option(help="The primer class")
    ] = PrimerClass.PRIMERSCHEMES.value,  # type: ignore
    collection: Annotated[
        Optional[list[Collection]],
        typer.Option(
            help="The collection tags. To provide multiple, use --collection '1' --collection '2'"
        ),
    ] = None,
    link_protocol: Annotated[
        list[str], typer.Option(help="Optional link to protocol")
    ] = [],
    link_validation: Annotated[
        list[str], typer.Option(help="Optional link to validation data")
    ] = [],
    links_homepage: Annotated[
        list[str], typer.Option(help="Optional link to homepage")
    ] = [],
    link_vendor: Annotated[
        list[str], typer.Option(help="Optional link to vendors")
    ] = [],
    link_misc: Annotated[
        list[str], typer.Option(help="Optional miscellaneous link")
    ] = [],
    fix: Annotated[bool, typer.Option(help="Attempt to fix the scheme")] = False,
    contact_info: Annotated[
        Optional[str], typer.Option(help="Contact information")
    ] = None,
    additional_files: Annotated[
        list[pathlib.Path],
        typer.Option(help="Additional files to include in the ./work directory"),
    ] = [],
    ref_select: Annotated[
        Optional[tuple[str, pathlib.Path]],
        typer.Option(help="Reference selection file. In the form 'chromosome file'"),
    ] = None,
):
    """Create a new scheme in the required format"""

    # Parse the primer.bed file
    try:
        headers, bedlines = BedLineParser().from_file(primerbed)
    except ValueError as e:
        raise typer.BadParameter(f"Error parsing {primerbed}: {e}") from e
    bedlines = BedFileModifier.sort_bedlines(bedlines)

    # get all primername versions
    primer_name_versions_to_name: dict[PrimerNameVersion, str] = {
        line.primername_version: line.primername for line in bedlines
    }

    if (
        len(primer_name_versions_to_name) > 1
        or PrimerNameVersion.V2 not in primer_name_versions_to_name
    ) and not fix:
        raise typer.BadParameter(
            f"Primernames ({[v for k, v in primer_name_versions_to_name.items() if k != PrimerNameVersion.V2]})"
            " are not in the correct format. Please update or try with --fix to attempt to parse."
        )

    if fix:
        # Attempt to fix the primer.bed file
        bedlines = BedFileModifier.update_primernames(bedlines)

    # Find the reference.fasta file
    reference_records = list(SeqIO.parse(reference, "fasta"))

    if len(reference_records) == 0:
        raise InvalidReference(f"Empty reference file {reference}")

    for record in reference_records:
        record.seq = record.seq.upper()

    # Validate the reference.fasta file
    validate_ref_records(reference_records)

    # Search for config.json
    config_json: None | dict = None
    if configpath is not None:
        config_json = json.load(configpath.open())
        assert isinstance(config_json, dict)
        # Remove some paths from the config
        config_json.pop("output_dir", None)
        # These hashes are no longer used, so remove to prevent confusion
        md5s_keys_to_remove = {k for k in config_json.keys() if k.endswith("md5")}
        for k in md5s_keys_to_remove:
            config_json.pop(k)

    # Multiple pngs/htmls/msas are allowed
    # The single check is mainly to prevent multiple schemes via providing the wrong directory
    # At this point we know we have a single scheme, due to having a single primer.bed, reference.fasta, and config.json

    pngs = [path for path in additional_files if path.name.endswith(".png")]

    # Create the collections set
    collections = {x for x in collection} if collection is not None else set()

    # Create the links set
    links = Links(
        protocols=link_protocol,
        validation=link_validation,
        homepage=links_homepage,
        vendors=link_vendor,
        misc=link_misc,
    )
    # Create the info.json
    # Generate the md5s
    info = Info(
        ampliconsize=ampliconsize,
        schemeversion=schemeversion,
        schemename=schemename,
        primer_bed_md5="NONE",  # Will be updated later
        reference_fasta_md5="NONE",  # Will be updated later
        status=schemestatus,
        citations=set(citations),
        authors=authors,
        algorithmversion=algorithmversion,  # type: ignore
        species=set(species),
        description=description,
        derivedfrom=derivedfrom,
        primerclass=primerclass,
        articbedversion=BedfileVersion.V3,
        collections=collections,
        links=links,
        contactinfo=contact_info,
    )

    # Parse ref_select
    if ref_select is not None:
        validate_ref_select_file(info, ref_select[0], ref_select[1], primerbed)

    #####################################
    # Final validation and create files #
    #####################################
    # Everything needs to be validated before creating files

    # Check if the repo already exists
    repo_dir = output / schemename / str(ampliconsize) / schemeversion
    if repo_dir.exists():
        raise SchemeExists(f"{repo_dir} already exists")
    repo_dir.mkdir(parents=True)

    # If this fails it will deleted the half completed scheme
    # Need to check the repo doesn't already exist
    try:
        # Write the primer.bed file
        BedLineParser().to_file(repo_dir / "primer.bed", headers, bedlines)

        # validate the bedfile
        # let the exception bubble up
        validate_bedfile(repo_dir / "primer.bed")

        # Write the reference.fasta file records
        with open(repo_dir / "reference.fasta", "w") as ref_file:
            SeqIO.write(reference_records, ref_file, "fasta")

        # Add the reference selection files
        if ref_select is not None:
            info.add_refselect(ref_select[1], ref_select[0], repo_dir / "info.json")

        # Update the hashes in the info.json
        info.primer_bed_md5 = hash_file(repo_dir / "primer.bed")
        info.reference_fasta_md5 = hash_file(repo_dir / "reference.fasta")

        working_dir = repo_dir / "work"
        working_dir.mkdir()

        if config_json is not None:
            # Write out the config.json
            with open(working_dir / "config.json", "w") as configfile:
                json.dump(config_json, configfile, indent=4, sort_keys=True)

        # Copy over misc files
        for file in additional_files:
            shutil.copy(file, working_dir / file.name)

        # Write out the info.json and readme
        generate_files(info, repo_dir, pngs=pngs)

    except Exception as e:
        # Cleanup
        shutil.rmtree(repo_dir)
        raise typer.BadParameter(f"{e}\nCleaning up {repo_dir}") from e


@app.command(no_args_is_help=True)
def build_index(
    gitaccount: Annotated[
        str,
        typer.Option(help="The name of the github account"),
    ] = "quick-lab",
    gitserver: Annotated[
        str,
        typer.Option(help="The name of the github server"),
    ] = "https://github.com/",
    parentdir: Annotated[
        pathlib.Path, typer.Option(help="The parent directory")
    ] = pathlib.Path("."),
    git_commit_sha: Annotated[
        Optional[str], typer.Option(help="The git commit")
    ] = None,
    force: Annotated[
        bool, typer.Option(help="Force the creation of the index.json")
    ] = False,
):
    """Build an index.json file from all schemes in the directory"""

    create_index(gitserver, gitaccount, parentdir, git_commit_sha, force)


@app.command(no_args_is_help=True)
def remove(
    schemeinfo: Annotated[
        pathlib.Path,
        typer.Argument(help="The path to info.json", readable=True, exists=True),
    ],
):
    """Remove a scheme's version from the repo, will also remove size and schemename directories if empty"""
    # Check that this is an info.json file (for safety)
    if schemeinfo.name != "info.json":
        raise typer.BadParameter(f"{schemeinfo} is not an info.json file")

    # Remove the schemeversion directory
    shutil.rmtree(schemeinfo.parent)

    # Move up the path and remove the size directory if empty
    size_dir = schemeinfo.parent.parent
    if len(list(size_dir.iterdir())) == 0:
        size_dir.rmdir()

    # Move up the path and remove the schemename directory if empty
    scheme_dir = size_dir.parent
    if len(list(scheme_dir.iterdir())) == 0:
        scheme_dir.rmdir()

    log.info(f"Removed {schemeinfo}")


if __name__ == "__main__":
    app()
