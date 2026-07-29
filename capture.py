#!/usr/bin/env python3

import argparse
import glob
import os
import stat
import sys


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    args = parser.parse_args()

    os.chdir(args.directory)

    file_types = {
        stat.S_IFDIR: "d",
        stat.S_IFREG: "f",
        stat.S_IFLNK: "l",
        stat.S_IFIFO: "p",
        stat.S_IFCHR: "c",
        stat.S_IFBLK: "b",
        stat.S_IFSOCK: "s",
    }

    for entry in glob.iglob("**", recursive=True):
        stats = os.lstat(entry)
        print(
            "%s\t%d\t%s\0%s\0"
            % (
                file_types[stat.S_IFMT(stats.st_mode)],
                stats.st_size,
                entry,
                os.readlink(entry) if os.path.islink(entry) else "",
            ),
            end="",
        )


if __name__ == "__main__":
    main()
