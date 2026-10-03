# Reference cases

Plans and certificates **frozen**, compared byte for byte.

A certificate produced in `1.2.0` must stay reproducible in `1.2.x`: any change of
behaviour of the oracle or of the certificate breaks a reference case, and that break
must be **visible in review**, not discovered by a user.
