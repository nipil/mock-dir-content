#!/usr/bin/env bash
set -e -u -o pipefail

# set mode
MODE=${MODE:-random}

# set logging
LOG_LEVEL=${LOG_LEVEL:-warning}

# First, load the script in a variable so you can use it without uploading its content
CAPTURE=$(cat capture.py)

# Then setup your source variables for easier invocation
SRC_DIR=${SRC_DIR:-$(pwd)/test-in}
OUTPUT=${OUTPUT:-capture.out}

# Then execute the capture (may be done remotely, see README.md)
python3 -c "${CAPTURE}" --log-level "${LOG_LEVEL}" "${SRC_DIR}" > "${OUTPUT}"

# OPTIONAL: To get a view of the output, convert it to hexadecimal
[ -n "${DEBUG_HEX:-}" ] && od -t x1a "${OUTPUT}"

# Secondly, load the script in a variable so you can use it without uploading its content
EXPAND=$(cat expand.py)

# Then setup your target variables for easier invocation
TGT_DIR=${TGT_DIR:-$(pwd)/test-out}

# OPTIONAL: remove the target directory first
[ -n "${CLEAN_TARGET:-}" ] && rm -Rf "${TGT_DIR}"

# Finally execute the expansion (may be done remotely, see README.md)
cat "${OUTPUT}" | python3 -c "${EXPAND}" --log-level "${LOG_LEVEL}" "${TGT_DIR}" "${MODE}"
