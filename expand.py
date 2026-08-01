#!/usr/bin/env python3

import argparse
import enum
import json
import logging
import os
import random
import sys

UTF_8 = "utf-8"


class UnknownKind(Exception):
    pass


class AppError(Exception):
    pass


class InvalidRecord(AppError):
    pass


class Mode(enum.IntEnum):
    EMPTY = 1
    RANDOM = 2
    SPARSE = 3


class Reader:
    def __init__(self, *, chunk_size, logger):
        self.buf = bytearray()
        self.read_size = chunk_size
        self.logger = logger

    def records(self):
        while True:
            # build input buffer from chunks of stdin
            chunk = sys.stdin.buffer.read(self.read_size)
            if not chunk:
                if len(self.buf) > 0:
                    InvalidRecord(f"Invalid record tail {self.buf!r}")
                return (None, None, None, None)
            self.buf.extend(chunk)

            # yield all the records from the buffer
            while True:

                # no full record available
                nul1 = self.buf.find(b"\0")
                if nul1 == -1:
                    break
                nul2 = self.buf.find(b"\0", nul1 + 1)
                if nul2 == -1:
                    break

                # extract record parts
                record = self.buf[: nul2 + 1]
                self.buf = self.buf[nul2 + 1 :]
                parts = record[:nul1].split(b"\t")
                exc = InvalidRecord(f"Invalid record parts {record!r}")
                if len(parts) != 3:
                    raise exc

                # parse record
                try:
                    kind = parts[0].decode(UTF_8)
                    digits = parts[1].decode(UTF_8)
                    path = parts[2].decode(UTF_8)
                except UnicodeDecodeError:
                    raise exc
                try:
                    size = int(digits)
                except ValueError:
                    raise exc

                yield (kind, size, path, record[nul1 + 1 : nul2])


class Writer:
    def __init__(self, mode, *, chunk_size, logger):
        self.mode = mode
        self.chunk_size = chunk_size
        self.logger = logger
        self.expanded = 0
        self.skipped = 0
        self.records = 0

    def create_file(self, path, size):
        with open(path, "wb") as file:
            if self.mode == Mode.EMPTY:
                pass  # do nothing
            elif self.mode == Mode.RANDOM:
                while size > 0:
                    amount = min(size, self.chunk_size)
                    data = os.urandom(amount)
                    file.write(data)
                    size -= amount
            elif self.mode == Mode.SPARSE:
                file.truncate(size)
            else:
                raise AppError(f"Unknown mode {self.mode!r}")

    def expand(self, record):
        self.logger.debug(f"Got {record=}")

        kind, size, path, link = record

        self.records += 1
        # TODO: reuse for flushing stdout ?
        if self.records & ((1 << 10) - 1) == 0:
            self.logger.info(
                f"Progress: records={self.records} expanded={self.expanded} skipped={self.skipped} path={path[:30]}..."
            )

        if kind == "d":
            try:
                os.mkdir(path)
            except FileExistsError:
                pass
        elif kind == "l":
            try:
                os.symlink(bytes(link), path)
            except FileExistsError:
                pass
        elif kind == "f":
            self.create_file(path, size)
        else:
            self.skipped += 1
            raise UnknownKind(f"Unknown record kind for {record!r}")
        self.logger.debug(f"Created {kind=} {path=}")
        self.expanded += 1

    def report(self):
        return {
            "expanded": self.expanded,
            "skipped": self.skipped,
            "records": self.records,
        }


def run(directory, mode, *, chunk_size, logger):
    try:
        os.mkdir(directory)
    except FileExistsError:
        pass
    os.chdir(directory)

    reader = Reader(
        chunk_size=chunk_size,
        logger=logger,
    )

    writer = Writer(
        mode,
        chunk_size=chunk_size,
        logger=logger,
    )

    # cannot use ThreadPoolExecutor for parallelism : parents must exist before children
    for record in reader.records():
        try:
            writer.expand(record)
        except UnknownKind as exc:
            logger.warning(exc)

    print(json.dumps(writer.report()))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=2**12)
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="warning",
    )
    parser.add_argument("directory")
    parser.add_argument("mode", choices=["empty", "random", "sparse"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(levelname)s: %(message)s",
    )

    logger = logging.getLogger(__name__)

    try:
        mode = getattr(Mode, args.mode.upper())
    except AttributeError:
        raise ValueError("Invalid mode: {args.mode!r}")

    try:
        run(
            args.directory,
            mode,
            chunk_size=args.chunk_size,
            logger=logger,
        )
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        logger.error(f"Error: {exc}")
        sys.exit(2)
    except AppError as exc:
        logger.critical(f"Critical: {exc}")
        sys.exit(3)


if __name__ == "__main__":
    main()
