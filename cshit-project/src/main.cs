#import "src/std.cs"

fn main() -> int:
    stdin: ptr = fdopen(0, "r")
    stdout: ptr = fdopen(1, "w")
    num: int = 0

    fprintf(stdout, "number:")
    fflush(stdout)
    fscanf(stdin, "%d", &num)

    while num != 67:
        fprintf(stdout, "number:")
        fflush(stdout)
        fscanf(stdin, "%d", &num)
    else:
        fprintf(stdout, "SIX SEVEN\n")

    return 0