# Adding a scheme

> See [primal-page create](cli.md#primal-page-create) full details.

To add a scheme into ```quick-lab/primerschemes```, primal-page is used to create the info.json metadata file and insure all the files are in the correct format. 

## Creating a scheme from primalscheme(1) files

### .primer.bed
From primalscheme a file should be output called `{scheme-name}.primer.bed`. This file contains all the data needed to produce the primer scheme.

> Old version of primalscheme do not contains the 7th column (PrimerSequence)

![primerbed](assets/primalscheme1bed.png)

### Using `primal-page`

![primerbed](assets/primal-page-create.png)

`primal-page` provides lots of options for creating the metadata. However, most of these are optional.

#### Required options
| Option               | Description                                    |
| -------------------- | ---------------------------------------------- |
| `--schemename`       | The name of the scheme                         |
| `--ampliconsize`     | The amplicon size                             |
| `--schemeversion`    | The version of the scheme                      |
| `--species`          | The `taxid` of the target species              |
| `--authors`          | The authors of the scheme                      |
| `--schemestatus`     | The status of the scheme                       |
| `--primerbed`        | A .bed file containing the primers             |
| `--reference`        | A .fasta file containing the reference genomes |
| `--output`           | Where to create the files                      |
| `--algorithmversion` | Which version was used (`primalscheme1`)       |

The requirements of these settings are listed in the [cli](cli.md)

```
primal-page create --schemename example-scheme --ampliconsize 400 --schemeversion v1.0.0 --species 1 --authors 'John Smith'  --authors 'Jane Doe' --schemestatus draft --primerbed {path to file} --reference {path to file} --output {~/primerschemes/primerschemes} --algorithmversion primalscheme1
```


## Manual editing of files

Do not do this unless you have to.

If you edit the `info.json` use `primal-page modify regenerate {info.json}` to validate the changes, and regenerate the README.md

If you edit the `primer.bed` or `reference.fasta` use `primal-page dev regenerate {info.json}` to update the hashes in the info.json. This reads `primer.bed` and `reference.fasta` as they are and never modifies them.

To re-sort `primer.bed` and update the primernames to the current version, use `primal-page dev reformat {info.json}`. This rewrites `primer.bed` and `reference.fasta` in place (it will prompt first, pass `--yes` to skip), then regenerates the info.json and README.md.

> If you are editing `primer.bed` or `reference.fasta` something has gone wrong


### Modifying cascade graph
```mermaid
flowchart TD

info[info.json]
readme[README.md]
primer[primer.bed]
ref[reference.fasta]


info -->|Embedded| readme

primer -->|md5 hash| info
ref -->|md5 hash| info

```
