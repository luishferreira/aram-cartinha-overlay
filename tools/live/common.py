import unicodedata


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c.casefold() for c in text if c.isalnum())
