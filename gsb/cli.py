# Command-line interface
from argparse import ArgumentParser


def generate_parsers() -> tuple[ArgumentParser, dict[str, ArgumentParser]]:
    """Generate the command-line parsers

    Returns
    -------
    gsb_parser : ArgumentParser
        The top-level argument parser responsible for routing arguments to
        specific action parsers
    action_parsers : dict of str to ArgumentParser
        The verb-specific argument parsers
    """
    raise NotImplementedError
