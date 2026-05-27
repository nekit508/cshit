#import "src/std.cs"

fn test() -> int:
    a: int = 1

    if a == 1:

        b: int = 2

        if b > 1:

            c: int = 3

            return c

        return b

    return 0


fn main() -> int:
    fprintf(fdopen(1, "w"), "test: %d\n", test())
    return 0