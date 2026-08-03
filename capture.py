#!/usr/bin/env python3

import os
import stat
import sys

from argparse import ArgumentParser
from logging import Logger
from typing import List, Optional, Tuple

PROGRESS_POW2 = 13

FILE_TYPES = {
    stat.S_IFDIR: "d",
    stat.S_IFREG: "f",
    stat.S_IFLNK: "l",
    stat.S_IFIFO: "p",
    stat.S_IFCHR: "c",
    stat.S_IFBLK: "b",
    stat.S_IFSOCK: "s",
}


class AppError(Exception):
    pass


def get_logger(log_level: str) -> Logger:
    # local scoping to avoid using the global module functions elsewhere
    import logging

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(levelname)s: %(message)s",
    )
    return logging.getLogger(__name__)


def main(argv: Optional[List[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    parser = ArgumentParser()
    parser.add_argument(
        "--log-missing",
        action="store_true",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="warning",
    )
    parser.add_argument("directory", nargs="*", default=["."])
    args = parser.parse_args()

    logger = get_logger(args.log_level)

    captures = 0
    missing = 0
    try:
        # single threade iterative processing, because
        # - multiple seek on HDD make things worse
        # - multiple seek on SSD are basically free
        # - but most important, once it is cached it's too fast
        # so keep simple and avoid unnecessary complexity
        for directory in args.directory:
            dir_captures, dir_missing = run(
                directory,
                logger=logger,
                log_missing=args.log_missing,
            )
            logger.info(
                f"Finished: captures={dir_captures} missing={dir_missing} directory={directory}"
            )
            captures += dir_captures
            missing += dir_missing
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        logger.error(f"Error: {exc}")
        sys.exit(2)
    except AppError as exc:
        logger.critical(f"Critical: {exc}")
        sys.exit(3)

    logger.info(f"Finished: captures={captures} missing={missing}")


def run(
    directory: str,
    *,
    log_missing: bool,
    logger: Logger,
) -> Tuple[int, int]:
    captures = 0
    missing = 0

    # move to base directory once, all sub path are relative to this path
    logger.info(f"Move into capture directory={directory}")
    os.chdir(directory)

    directories = [directory]
    while len(directories) > 0:
        directory = directories.pop()

        # process the given item (read directory)
        logger.debug(f"Processing capture sub-directory={directory}")
        for entry in os.scandir(directory):

            # iterative processing of a recursive filesystem
            if entry.is_dir(follow_symlinks=False):
                directories.append(entry.path)
                logger.debug(f"Queuing directory: entry={entry.path}")
                # IMPORTANT: do NOT use `continue` as we want the direcotry itself be displayed !

            # provide progress feedback every 2**N records
            captures += 1
            # TODO: reuse for flushing stdout ?
            if captures & ((1 << PROGRESS_POW2) - 1) == 0:
                logger.info(
                    f"Progress: captures={captures} missing={missing} entry={entry.path}"
                )

            # extracts stats and (if applicable) link info
            link = ""
            try:
                stats = entry.stat(follow_symlinks=False)
                if entry.is_symlink():
                    link = os.readlink(entry.path)
            except FileNotFoundError:
                missing += 1
                if log_missing:
                    logger.warning(f"Not found: entry={entry.path}")
                continue

            # build the record and print it to stdout
            record = (
                FILE_TYPES[stat.S_IFMT(stats.st_mode)],
                stats.st_size,
                entry.path,
                link,
            )
            logger.debug(f"Found {record!r}")
            print(
                "%s\t%d\t%s\0%s\0" % record,
                end="",
            )

    return (captures, missing)


if __name__ == "__main__":
    main()
