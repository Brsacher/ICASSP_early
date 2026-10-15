#!/bin/sh
# Fetch the five frozen-input archives from the GitHub release and unpack
# them under $FA_ART_ROOT.
#
#   bash data/download.sh
#   bash data/download.sh --from-dir /path/to/archives
#
# --from-dir skips the download. The directory must already contain the five
# tar.zst files. The script checks them against data/SHA256SUMS and unpacks.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
FA_DATA_ROOT=${FA_DATA_ROOT:-$ROOT/data}
FA_ART_ROOT=${FA_ART_ROOT:-$ROOT/artifacts}
FROM_DIR=""
RELEASE="https://github.com/Brsacher/ICASSP_early/releases/download/icassp2027-submission"
PACKS="velox_streams_cadets.tar.zst velox_streams_theia.tar.zst frozen_labels.tar.zst kairos_streams.tar.zst orthrus_streams.tar.zst"

while [ $# -gt 0 ]; do
    case "$1" in
        --from-dir)
            if [ $# -lt 2 ]; then
                echo "--from-dir needs a directory" >&2
                exit 2
            fi
            FROM_DIR=$2
            shift 2
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

mkdir -p "$FA_DATA_ROOT" "$FA_ART_ROOT"

if [ -z "$FROM_DIR" ]; then
    for name in $PACKS; do
        echo "fetch $name"
        curl -fL --retry 3 -o "$FA_DATA_ROOT/$name" "${RELEASE}/${name}"
    done
    FROM_DIR=$FA_DATA_ROOT
fi

(
    cd "$FROM_DIR"
    sha256sum -c "$ROOT/data/SHA256SUMS"
)
for name in $PACKS; do
    tar --zstd -C "$FA_ART_ROOT" -xf "$FROM_DIR/$name"
done
echo "unpacked into $FA_ART_ROOT"
