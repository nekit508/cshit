


def pretty_list(lst: list, sep=", ") -> str:
    return sep.join(repr(l) for l in lst)

def pretty_dict(dct: dict, sep=", ") -> str:
    return sep.join(f"{repr(key)}:{repr(dct[key])}" for key in dct)

def single_entry(field: str = "__single_entry_marker__", arg: int = 1):
    def deco(func):
        def wrapper(*args):
            ast = args[arg]
            if hasattr(ast, field):
                return getattr(ast, field)
            out = func(*args)

            setattr(ast, field, out)
            return out

        return wrapper
    return deco