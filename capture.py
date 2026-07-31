#!/usr/bin/env python3

import os
import stat
import sys

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from logging import Logger
from queue import Empty, Queue
from threading import Event
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
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count(),
    )
    parser.add_argument("directory")
    args = parser.parse_args()

    logger = get_logger(args.log_level)

    try:
        run(
            args.directory,
            workers=args.workers,
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


def run(
    directory: str,
    *,
    workers: int,
    log_missing: bool,
    logger: Logger,
) -> None:
    captures = 0
    missing = 0

    # move to base directory once, all sub path are relative to this path
    os.chdir(directory)

    # iterative processing of a recursive filesystem
    directory_queue = Queue()
    directory_queue.put(".")

    # sentinel flag to signal the workers to exit
    exit_event = Event()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # create many workers, all polling directories from the queue
        futures = [
            executor.submit(
                directory_worker,
                directory_queue,
                worker_id=worker_id,
                exit_event=exit_event,
                log_missing=log_missing,
                logger=logger,
            )
            for worker_id in range(workers)
        ]

        # wait for the queue to become empty, signaling work is totally finished
        try:
            directory_queue.join()
        except KeyboardInterrupt:
            logger.info("User requested exit")
        finally:
            # signal the workers they can stop processing
            exit_event.set()

        # poll the worker futures until they exit
        for future in futures:
            # if a worker thread raised an exception, calling
            # result() will re-raise it in the main thread
            (worker_captures, worker_missing) = future.result()
            # sum up stats
            captures += worker_captures
            missing += worker_missing

    logger.info(f"Finished: captures={captures} missing={missing}")


def directory_worker(
    directory_queue: Queue,
    *,
    exit_event: Event,
    log_missing: bool,
    logger: Logger,
    worker_id: int,
) -> Tuple[int, int]:
    logger.info(f"Worker {worker_id} started")

    worker_captures = 0
    worker_missing = 0

    try:
        # infinite loop until caller sends sentinel value
        while True:
            # comply with exit requests
            if exit_event.is_set():
                return (worker_captures, worker_missing)

            # get an item to process, but with timeout, which is useful
            # in cas the worker is already waiting on queue before the
            # exit_event is set, otherwise it would never stop waiting
            try:
                directory = directory_queue.get(timeout=0.1)
            except Empty:
                continue

            try:
                captures, missing = process_directory(
                    directory,
                    directory_queue,
                    worker_id=worker_id,
                    log_missing=log_missing,
                    logger=logger,
                )
            finally:
                # notify that the work item has actually been done, because
                # an empty queue does not mean worker have finished working !
                directory_queue.task_done()

            worker_captures += captures
            worker_missing += missing

    finally:
        logger.info(
            f"Worker {worker_id} finished: captures={worker_captures} missing={worker_missing}"
        )


def process_directory(
    directory: str,
    directory_queue: Queue,
    *,
    log_missing: bool,
    logger: Logger,
    worker_id: int,
) -> Tuple[int, int]:
    captures = 0
    missing = 0

    # process the given item (read directory)
    for entry in os.scandir(directory):

        # iterative processing of a recursive filesystem
        if entry.is_dir(follow_symlinks=False):
            directory_queue.put(entry.path)
            logger.debug(f"Queuing directory: entry={entry.path}")
            # IMPORTANT: do NOT use `continue` as we want the direcotry itself be displayed !

        # provide progress feedback every 2**N records
        captures += 1
        if captures & ((1 << PROGRESS_POW2) - 1) == 0:
            logger.info(
                f"Worker {worker_id}: captures={captures} missing={missing} entry={entry.path}"
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
