# Why not an image

A reviewer trained in computer vision will ask for a CNN on the rasterized plan.
It is the most tempting trap of the project, and it kills it.

Moving a wall by 2 cm — exactly the Frank-Wolfe move — changes **no pixel** of an
image at room resolution. The gradient of the network with respect to the decision
variables \(x,y,w,h\) is then zero almost everywhere. The linear oracle receives
\(c=0\), and the optimizer is blind.

The surrogate's input is therefore a **set of tokens** that are continuous in the
geometry (`light.tokens.plan_to_tokens`). The anti-image test
(`test_jetons_continus`) fails if a 2 cm displacement leaves the tokens unchanged.

`ARCHITECTURE.md` §10 makes it a fatal anti-pattern. It is not an implementation
preference.
