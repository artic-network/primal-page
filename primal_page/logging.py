import logging

from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[
        RichHandler(
            markup=True,
            keywords=["README.md", "info.json", "primer.bed", "reference.fasta"],
        ),
    ],
)

log = logging.getLogger("rich")
