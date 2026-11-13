# -*- encoding: utf-8 -*-
"""
witopnet.app.cli module

"""

import os

import multicommand
from keri.app.directing import runController
from keri import help

from witopnet.app.cli import commands

logger = help.ogler.getLogger()


def main():
    """Entry point for the witopnet CLI.

    Builds the argument parser from the commands package, dispatches to the
    appropriate subcommand handler, and runs the resulting doers under a Doist
    event loop. Prints usage if no subcommand is given.
    """
    parser = multicommand.create_parser(commands)
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    try:
        doers = args.handler(args)
        runController(doers=doers, expire=0.0)  # Doist tick from KERI_DOIST_TOCK

    except Exception as ex:
        if os.getenv("DEBUG_WITOPNET"):
            import traceback

            traceback.print_exc()
        else:
            print(f"ERR: {ex}")
        return -1


if __name__ == "__main__":
    main()
