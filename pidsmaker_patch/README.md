# PIDSMaker patch

`2026-09-18_tgn_eval_oom.patch` edits `pidsmaker/tgn.py`.

It splits the eval-mode all-node memory flush into chunks of 262144 nodes so Kairos and ORTHRUS validation does not allocate the full node set at once. The flush still covers every node. It does not change the message store.

This change is **not in the PIDSMaker commit that this experiment tracks** (`84d9314`). The lab working tree had the patch applied; `git diff 84d9314 HEAD -- pidsmaker/tgn.py` is empty. VELOX training does not need it. Apply it only when running Kairos or ORTHRUS evaluation:

```bash
git apply pidsmaker_patch/2026-09-18_tgn_eval_oom.patch
```

Remove it with `git apply -R`.
