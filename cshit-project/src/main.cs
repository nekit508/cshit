#import "src/std.cs"

stdout: ptr = 0
stdin: ptr = 0

fn open_stdout() -> ptr:
    return fdopen(1, "w")

fn open_stdin() -> ptr:
    return fdopen(0, "r")

fn main() -> int:
    stdout = open_stdout()
    stdin = open_stdin()

    number: int
    fputs("Enter ur number: ", stdout)
    fflush(stdout)
    fscanf(stdin, "%d", &number)
    fprintf(stdout, "%s %d\n", "Your number is", number)

    if number > 67:
        fprintf(stdout, "Bigger than 67\n")
    elif number < 67:
        fprintf(stdout, "Less than 67\n")
    else: fprintf(stdout, "SIX SEVEN\n")

    fflush(stdout)
    fscanf(stdin, "\n")

    return 0