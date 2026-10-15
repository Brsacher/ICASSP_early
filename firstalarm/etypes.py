"""Edge types and emit-end rules."""

from __future__ import annotations

# pidsmaker is only needed for assert_rel2id (stream rebuild). Load-only v9 never calls it.

CONNECT = 1
EXECUTE = 2
OPEN = 3
READ = 4
RECVFROM = 5
RECVMSG = 6
SENDMSG = 7
SENDTO = 8
WRITE = 9
CLONE = 10

EMIT_DST = frozenset({READ, RECVFROM, RECVMSG, EXECUTE, OPEN})
EMIT_SRC = frozenset({WRITE, SENDTO, SENDMSG, CONNECT, CLONE})
PRODUCER = frozenset({WRITE, SENDTO, SENDMSG})
CONSUMER = frozenset({READ, EXECUTE, RECVFROM, RECVMSG})

NTYPE = {"subject": 0, "file": 1, "netflow": 2, "unknown": 3}
NTYPE_NAME = ("subject", "file", "netflow", "unknown")

ETYPE_NAME = {
    CONNECT: "CONNECT",
    EXECUTE: "EXECUTE",
    OPEN: "OPEN",
    READ: "READ",
    RECVFROM: "RECVFROM",
    RECVMSG: "RECVMSG",
    SENDMSG: "SENDMSG",
    SENDTO: "SENDTO",
    WRITE: "WRITE",
    CLONE: "CLONE",
}


def assert_rel2id() -> None:
    from pidsmaker.utils.dataset_utils import rel2id_darpa_tc

    want = {
        "EVENT_CONNECT": CONNECT,
        "EVENT_EXECUTE": EXECUTE,
        "EVENT_OPEN": OPEN,
        "EVENT_READ": READ,
        "EVENT_RECVFROM": RECVFROM,
        "EVENT_RECVMSG": RECVMSG,
        "EVENT_SENDMSG": SENDMSG,
        "EVENT_SENDTO": SENDTO,
        "EVENT_WRITE": WRITE,
        "EVENT_CLONE": CLONE,
    }
    for k, v in want.items():
        if rel2id_darpa_tc[k] != v:
            raise AssertionError(f"rel2id mismatch {k}: {rel2id_darpa_tc[k]} != {v}")
