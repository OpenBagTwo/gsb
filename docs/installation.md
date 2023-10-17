# Installation

[![PyPI version](https://badge.fury.io/py/gsb.svg)](https://badge.fury.io/py/gsb)
![PyPI downloads](https://img.shields.io/pypi/dm/gsb.svg)

The `gsb` package has minimal dependencies and should run on pretty much any computer
or operating system. It does require **Python 3.11 or newer**, however, so
the first step is making sure that requirement is met.

To do so, open a terminal and run:

```bash
python -V
```

If you get a message that no such command or executable exists, or if the version
that's returned is before 3.11, you'll first need to install an up-to-date
Python runtime.

!!! tip "Recommendation"
    The easiest and safest option is to install a
    [miniconda](https://docs.conda.io/en/latest/) distribution (I strongly
    recommend [mambaforge](https://github.com/conda-forge/miniforge#mambaforge)).
    This can be done on almost any computer and requires no admin privileges.

## Installing `gsb`

### Using pipx

The easiest way to install GSB if you're using the system Python is via
[pipx](https://pypa.github.io/pipx/):

```bash
pipx install gsb[test]
```

_You may omit the `[test]` extra if you really want, but it's a good idea
for [making sure that GSB is fully compatible with your system.](#verifying-your-installation)_

### Inside a conda environment

These instructions assume that you've already downloaded and installed mambaforge
or another conda distribution and that mamba/conda is already registered
to your system path.

1. Open a terminal (miniforge prompt on Windows) and create a new virtual environment via:
   ```bash
   mamba create -n gsb "python>=3.11" "pip>22"
   ```
   (substitute `conda` for `mamba` as needed)

1. Activate your new environment:
    ```bash
    conda activate gsb
    ```

Then continue onto the next section.

### Installation via pip

Whether you're using conda or another virtual environment manager (_e.g._ venv),
to actually install GSB within your virtual environment, first make sure that
the environment is activated, then:

3. Install `gsb` from PyPI using pip:
    ```bash
    python3 -m pip install --user gsb[test]
    ```

#### Bleeding Edge

If you'd like to test out upcoming features or help with beta testing, you
can install from the current development branch via:

```bash
python -m pip install --user git+https://github.com/OpenBagTwo/gsb.git@dev#egg=gsb[test]
```

**Be warned** that any code on this branch is considered highly experimental. Given that this
is a tool for _managing backups_, make sure that you are not using it on any data that isn't
also being backed up in another way.

## Verifying Your Installation

The instructions above recommend installing `gsb` with the optional `[test]`
extra to enable easy running of GSB's included test suite. Doing so will ensure
that GSB is able to work with your file system and that all of the dependcies
and shared libraries are interacting correctly. Run this test suite by opening
a suitable command line and running the command:

```bash
gsb test
```

If all tests pass, then you're good to go!

!!! note "conda/venv users:"
    If you get an error that `gsb` was not found, first make sure to activate its
    virtual environment, then try again.

    If you'd like `gsb` to be available outside of your virtual environment,
    you can copy the executable to somewhere within your system path, _e.g._ for
    Linux, starting with the virtual environment deactivated:
    ```bash
    $ echo $PATH
    /home/openbagtwo/.mambaforge/condabin:/home/openbagtwo/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin
    $ conda activate gsb
    $ which gsb
    /home/openbagtwo/.mambaforge/envs/gsb/bin/gsb
    $ cp /home/openbagtwo/.mambaforge/envs/gsb/bin/gsb ~/.local/bin/
    ```
