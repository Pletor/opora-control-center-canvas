"""Policy identities must round-trip through JSON clients without precision loss."""


def safe_id(value):
    return type(value) is int and 1 <= value <= 9007199254740991
