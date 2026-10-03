# Dual diagnostics

**Problem.** The plan is valid and the sDA bound is known, but we do not know
**which constraint** prevents the south room from opening further. Move a
load-bearing wall back by 20 cm, or widen the corridor?

**Solution.**

```python
import numpy as np
from scipy import sparse

from archlux.certify.dual import translate_duals
from archlux.geom.polytope import Polytope

poly = Polytope(
    A=sparse.csr_matrix(np.eye(3)),
    b=np.ones(3),
    A_eq=sparse.csr_matrix((0, 3)),
    b_eq=np.zeros(0),
    bounds=((0.0, 1.0),) * 3,
    index={"a.x": 0, "a.y": 1, "a.w": 2},
    origins=(
        "load-bearing wall axis 3",
        "kitchen minimum area",
        "passage width",
    ),
)
for sentence, price in translate_duals(np.array([-4.1, -1.7, 0.0]), poly):
    print(f"{price:+.1f}  {sentence}")
```

The dual prices come from the same LP as legalization (`lmo.solve(...,
duals=True)`). `Polytope.origins` makes them readable; a bare row index
does not. Zero prices (inactive constraints) are filtered out.

**Result.**

```
-4.1  load-bearing wall axis 3: relaxing it by 10 cm would change the total displacement by -0.41 m (valid for small changes only, a few tens of cm)
-1.7  kitchen minimum area: relaxing it by 10 cm would change the total displacement by -0.17 m (valid for small changes only, a few tens of cm)
```

The raw price (`-4.1`) is the change of the objective per metre of relaxation; the sentence
converts it for a 10 cm notch (`step_m`) and into the unit of the objective: metres of
total displacement in classic mode, points of the **predicted** indicator in performance
mode. Unknown labels (like the ones of this example) are kept as they are;
those of the real polytope are rephrased ("load-bearing wall p1 at x = 6 m : …"), and the
rows of the L1 epigraph, which are solver artefacts, are never reported.

**What to remember.** A dual price is a *local* derivative. Moving the
wall back by 20 cm is within the announced range; moving it back by 2 m is
not. Neither a geometric repairer nor a simulator alone produces these
lines: they come from the fusion polytope × daylight objective.

**See also:** [Farkas and duals](../formulas/farkas.md),
[Read a certificate](04-read-a-certificate.md),
[The polytope](../concepts/polytope.md).
