#import "src/std.cs"

fn open_stream(descr: int) -> char*:
    return fdopen(descr, "w")

fn main() -> int:
    stream: char* = open_stream(1)
    if stream == 0:
        return 67
    fputs("Hello, world!", stream)
    fclose(stream)
    Sleep(5000)
    return 0