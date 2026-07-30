#!/usr/bin/env python3

import argparse
import logging
import os
import stat
import sys


class AppError(Exception):
    pass


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-missing",
        action="store_true",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="warning",
    )
    parser.add_argument("directory")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(levelname)s: %(message)s",
    )

    logger = logging.getLogger(__name__)

    try:
        run(
            args.directory,
            logger=logger,
            log_missing=args.log_missing,
        )
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        logger.error(f"Error: {exc}")
        sys.exit(2)
    except AppError as exc:
        logger.critical(f"Critical: {exc}")
        sys.exit(3)


def run(directory, *, log_missing, logger):
    captures = 0
    missing = 0

    os.chdir(directory)

    file_types = {
        stat.S_IFDIR: "d",
        stat.S_IFREG: "f",
        stat.S_IFLNK: "l",
        stat.S_IFIFO: "p",
        stat.S_IFCHR: "c",
        stat.S_IFBLK: "b",
        stat.S_IFSOCK: "s",
    }

    # iterative processing of recursive filesystem
    directories = ["."]
    while len(directories) > 0:
        directory = directories.pop()

        for entry in os.scandir(directory):

            if entry.is_dir(follow_symlinks=False):
                directories.append(entry.path)
                logger.debug(f"Queuing directory {entry.path=}")
                continue

            captures += 1
            if captures & ((1 << 10) - 1) == 0:
                logger.info(
                    f"Progress: {captures=} {missing=} entry={entry.path[:30]}..."
                )

            link = ""
            try:
                stats = entry.stat(follow_symlinks=False)
                if entry.is_symlink():
                    link = os.readlink(entry.path)
            except FileNotFoundError:
                missing += 1
                if log_missing:
                    logger.warning(f"Not found: {entry}")
                continue

            record = (
                file_types[stat.S_IFMT(stats.st_mode)],
                stats.st_size,
                entry.path,
                link,
            )
            logger.debug(f"Found {record!r}")
            print(
                "%s\t%d\t%s\0%s\0" % record,
                end="",
            )


if __name__ == "__main__":
    main()
