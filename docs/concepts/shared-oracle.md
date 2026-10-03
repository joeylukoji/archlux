# The shared oracle

The linear oracle of Frank-Wolfe **is** the legalization solver. This is not a
metaphor: it is the same call, with another cost vector.

The block below runs as is. It takes the plan of
[gallery 01](../gallery/01-repair-a-plan.md) (two rooms that overlap by one metre),
builds the polytope of valid plans for the order read on the proposal, then calls
`lmo.solver.solve` twice: once for classic legalization, once for the step of one
Frank-Wolfe iteration.

```python
import archlux as ax
from archlux.api import gradient_distance
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, extend_l1_slack, vectorize
from archlux.light import AnalyticSurrogate
from archlux.lmo import solver as lmo

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=12.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=1.0),
)
poly = build_polytope(deduce_order(plan, structure=ctx.structure), ctx)
Q_proposed = vectorize(plan, poly.index)
n = len(poly.index)

# classic legalization — milestone 2: minimize the L1 distance to the proposal
poly_l1 = extend_l1_slack(poly, Q_proposed)
sol = lmo.solve(poly_l1, c=gradient_distance(Q_proposed))
Q = sol.x[:n]  # the first n coordinates; the following ones are the L1 slacks
assert sol.status == "optimal" and poly.contains(Q)

# one Frank-Wolfe iteration — milestone 3: same call, costs = -gradient of the surrogate
surrogate = AnalyticSurrogate()
sol = lmo.solve(poly, c=-surrogate.gradient(Q, ctx.orientation), start=Q)
S = sol.x  # a vertex of the polytope
gamma = 0.5  # step of the iteration
Q_next = Q + gamma * (S - Q)
assert poly.contains(S) and poly.contains(Q_next)
```

`lmo` ignores where \(c\) comes from. That ignorance is the heart of
`ARCHITECTURE.md`: one simplex, two uses. Adding a second solver
"for daylight" would break the guarantee that every iterate is a valid plan:
`Q_next` is an average of two points of the polytope, hence a point of the polytope,
which is convex.

This block shows the mechanism, not all of `legalize`. Before the loop, `legalize`
freezes the contacts of the legalized plan and adds the inner approximation of the
minimum areas and the displacement budget; the loop (`archlux.solve.frank_wolfe`)
takes the step \(2/(k+2)\), halves it while the objective decreases, adds
"away" steps, and stops when the Frank-Wolfe gap falls below the tolerance.

Warm start (`start=x` **at every** iteration) does not change the solution, only the
time: only the presence of `start` matters, it lets the model already built for this
polytope be reused. Omitting it in a 50-round loop costs a factor of 3 to 5.

The geometry stays **exact** (every iterate \(\in P\)). The surrogate's score stays
**without guarantee** until conformal prediction (milestone 5). Do not write
"optimal plan for daylight": write "valid plan that maximizes the surrogate,
optimization gap \(g\)".

See [Frank-Wolfe](../formulas/frank-wolfe.md),
[compare two methods](../gallery/02-compare-two-methods.md).
