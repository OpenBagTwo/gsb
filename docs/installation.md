# Installation

[![PyPI version](https://badge.fury.io/py/gsb.svg)](https://badge.fury.io/py/gsb)
![PyPI downloads](https://img.shields.io/pypi/dm/gsb.svg)

The `gsb` package has minimal dependencies and should run on pretty much any computer
or operating system. It does require **Python 3.11 or newer**
portable distributions (read: no need for admin privileges) of which
are available through miniconda and
[mambaforge](https://github.com/conda-forge/miniforge#mambaforge).

## Installing `gsb`

### Inside a conda environment

Skip this sub-section if you're using the system Python.

These instructions assume that you've already downloaded and installed mambaforge
or another conda distribution and that mamba/conda is already registered
to your system path.

1. Open a terminal (miniforge prompt on Windows) and create a new virtual environment via:
   ```bash
   mamba create -n gsb "python>=3.10" "pip>22"
   ```
   (substitute `conda` for `mamba` as needed, and skip this step and the next if
    you're using the system Python)

1. Activate your new environment:
    ```bash
    conda activate gsb
    ```

Then continue onto the next section.

### Installation via pip

3. Install `gsb` from PyPI using pip:
    ```bash
    python3 -m pip install --user gsb[test]
    ```

4. Ensure that `gsb` is compatible with your system by running:
    ```bash
    gsb test
    ```
    If all tests pass, then you're good to go!

!!! tip
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

## Bleeding Edge

If you'd like to test out upcoming features or help with beta testing, you
can install from the current development branch via:

```bash
python -m pip install --user git+https://github.com/OpenBagTwo/gsb.git@dev#egg=gsb[test]
```

**Be warned** that any code on this branch is considered highly experimental. Given that this
is a tool for _managing backups_ make sure that you are not using it on any data that isn't
also being backed up in another way.
