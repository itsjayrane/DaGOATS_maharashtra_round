"""Resolution v2: a BKT-style (Bayesian Knowledge Tracing) estimate of P(learner still holds a misconception).

Evidence = one transfer attempt on a problem that can reveal the misconception. 'clean' = a new task, every test
passes and the model does not detect the misconception. mastery = 1 - P.
A misconception is RESOLVED only when >= NEEDED_PROBLEMS different transfer problems are cleared AND P < P_RESOLVED.
"""
P_GUESS = 0.10      # P(clean transfer | still holds the misconception): got it right by luck / an easy case
P_SLIP = 0.10       # P(not clean | misconception gone): a slip, typo or unrelated bug
P_LEARN = 0.10      # P(the misconception disappears) per practice opportunity
P_MIN, P_MAX = 0.01, 0.95  # keep the estimate movable in both directions
P_RESOLVED = 0.15   # resolved only below this
NEEDED_PROBLEMS = 2  # ... and after this many DIFFERENT transfer problems were cleared


def clamp(p):
    return min(P_MAX, max(P_MIN, p))


def update(p, clean):
    """Posterior P(misconception) after one observation, then the learning transition."""
    p = clamp(p)
    if clean:
        post = p * P_GUESS / (p * P_GUESS + (1 - p) * (1 - P_SLIP))
    else:
        post = p * (1 - P_GUESS) / (p * (1 - P_GUESS) + (1 - p) * P_SLIP)
    return clamp(post * (1 - P_LEARN))


def is_resolved(p, cleared_problems):
    return len(cleared_problems) >= NEEDED_PROBLEMS and p < P_RESOLVED
