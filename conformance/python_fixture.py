"""Real separate procedure module used by the native Python contract suite."""

identity = object()


def combine(left, right):
    return [left + right, left - right, left * right]
