from pathlib import Path

from setuptools import setup

import versioneer

long_description = (Path(__file__).parent / "README.md").read_text()

setup(
    name="gsb",
    python_requires=">=3.11",
    description="Game Save Backups: A Git-Based Tool for Managing Your Save States",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Gili "OpenBagTwo" Barlev',
    url="https://github.com/OpenBagTwo/gsb",
    packages=[
        "gsb",
        "gsb.test",
    ],
    package_data={"gsb": ["py.typed"]},
    entry_points={
        "console_scripts": [
            "gsb = gsb.cli:gsb",
        ]
    },
    license="GPL v3",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=["pygit2>=1.12", "click>=8"],
    extras_require={"test": ["pytest>=7", "pytest-cov>=4"]},
)
