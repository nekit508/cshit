def pretty_list(lst: list, sep=", ") -> str:
    return sep.join(repr(l) for l in lst)

def pretty_dict(dct: dict, sep=", ") -> str:
    return sep.join(f"{repr(key)}:{repr(dct[key])}" for key in dct)