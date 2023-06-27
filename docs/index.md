# **G**ame **S**ave **B**ackups

[![PyPI version](https://badge.fury.io/py/gsb.svg)](https://badge.fury.io/py/gsb)
![PyPI downloads](https://img.shields.io/pypi/dm/gsb.svg)

![Linux](https://img.shields.io/badge/GNU/Linux-000000?style=flat-square&logo=linux&logoColor=white&color=eda445)
![SteamOS](https://img.shields.io/badge/SteamOS-3776AB.svg?style=flat-square&logo=steamdeck&logoColor=white&color=7055c3)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)
![MacOS](https://img.shields.io/badge/mac%20os-000000?style=flat-square&logo=apple&logoColor=white&color=434334)
![RaspberryPi](https://img.shields.io/badge/Raspberry%20Pi-000000?style=flat-square&logo=raspberrypi&logoColor=white&color=c51a4a)

[![python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat&logo=python&logoColor=white&color=ffdc53&labelColor=3d7aaa)](https://www.python.org)
[![coverage](https://openbagtwo.github.io/gsb/dev/img/coverage.svg)](https://openbagtwo.github.io/gsb/dev/coverage)
[![lint](https://openbagtwo.github.io/gsb/dev/img/pylint.svg)](https://openbagtwo.github.io/gsb/dev/lint-report.txt)


A tool for managing incremental backups of your save states _using Git!_

## In a Nutshell

Does Steam keep corrupting your cloud saves?

Does it take too long to create or restore a Minecraft backup?

Do you want to rewind your game five hours and explore _what might have been_ if
only you'd punched that NPC in the face?

If that sounds like you, then `gsb` is here to help! This is a lightweight wrapper
around the [Git](https://git-scm.com/) version control system that's optimized for
game saves. Features (will) include:

- automated incremental backups
- painless savegame restores
- easy history navigation
- revision history compression and cleaning
- support for branches
- workflows for implementing [3-2-1 backups](https://www.jeffgeerling.com/blog/2021/my-backup-plan)
- full compatibility with Git and other git-based tools...
- ... all without ever needing to know a thing about Git


## Installation

The `gsb` package is written for **Python 3.11** but otherwise
should run on any operating system and architecture.

The latest release can be installed from PyPI via `pip`:

```bash
$ python -m pip install --user gsb
```

Full installation instructions can be found on
[GitHub Pages](https://openbagtwo.github.io/gsb/dev/installation).

## Usage

The recommended way to interact with `gsb` is via its  command-line interface.
Once you've installed the package, run the following command to get an overview of the
available actions:

```bash
$ gsb --help
```

and use:

```bash
$ gsb <verb> --help
```
(_e.g._ `gsb backup --help`)

for further details on running each of those commands.

Full documentation, including tutorials, examples and full CLI docs, can be
found on [GitHub Pages](https://openbagtwo.github.io/gsb/).

### Quick-Start Guide

Coming soon!

## Contributing

If you're interested in helping develop this project, have a look at the
[repo backlog](https://github.com/OpenBagTwo/gsb/issues) and then read
through the
[contributor's guide](https://openbagtwo.github.io/gsb/dev/contrib).

## License

This project--the executable, source code and all documentation--are published
under the
[GNU Public License v3](https://github.com/OpenBagTwo/gsb/blob/dev/LICENSE),
and any contributions to or derivatives of this project _must_ be licensed under
compatible terms.
