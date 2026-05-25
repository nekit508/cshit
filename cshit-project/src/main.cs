#import "src/std.cs"

fn open_stdout() -> char*:
    return fdopen(1, "w")

fn main() -> int:
    stdout: char* = open_stdout()
    stream: ptr = fopen("build/file.txt", "w")

    if stream == 0:
        fputs("Cannot access file!", stdout)
    else:
        fputs("Hello, world!", stream)
        fclose(stream)

    fclose(stdout)
    Sleep(5000)
    return 0