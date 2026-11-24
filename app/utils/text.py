import unicodedata


def normalized(value):
    decomposed = unicodedata.normalize("NFKD", str(value))
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split())
