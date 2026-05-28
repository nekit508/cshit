#import "src/std.cs"

struct Stream:
    handle: ptr

    fn __init__(descriptor: int, mode: char*) -> void:
        self.handle = fdopen(descriptor, mode)

    fn close() -> void:
        fclose(self.handle)


fn main() -> int:
    stdin: ptr = fdopen(0, "r")
    stdout: ptr = fdopen(1, "w")
    num: int = 0

    do:
        fprintf(stdout, "number:")
        fflush(stdout)
        fscanf(stdin, "%d", &num)
    while num != 67
    else:
        fprintf(stdout, "SIX SEVEN\n")

    return 0