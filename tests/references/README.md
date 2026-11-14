# Reference cases

Plans and certificates **frozen**, compared byte for byte.

A certificate produced in `1.2.0` must stay reproducible in `1.2.x`: any change of
behaviour of the oracle or of the certificate breaks a reference case, and that break
must be **visible in review**, not discovered by a user.

## Cases

| File | Plan | What it pins |
|---|---|---|
| `legalize_t2.json` | `examples/t2.json` | Two-bedroom plan, tiling, example regulation |
| `legalize_t3_load_bearing.json` | `examples/t3_load_bearing.json` | Load-bearing walls kept on their line |
| `legalize_generated.json` | `examples/generated.json` | A generator-like plan with gaps and overlaps |
| `legalize_synthetic_0_a025.json` | B1 corpus plan 0, fault 0.25 m | Synthetic repair, minima at 80 % |
| `legalize_synthetic_1_a050.json` | B1 corpus plan 1, fault 0.50 m | Synthetic repair, larger fault |
| `neutrality.json` | — | Neutrality check of `scripts/neutrality.py` |

`tests/test_references.py` regenerates each case and compares it byte for byte. To
refreeze after an intended change: `ARCHLUX_FREEZE=1 pytest tests/test_references.py`.
