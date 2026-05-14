from Levenshtein import distance


def calculate_alias_distance(alias1: str, alias2: str) -> int:
    """Calculate the Levenshtein distance between two aliases."""
    return distance(alias1, alias2)
