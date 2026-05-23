#import "src/std.cs"

fn main() -> int:
    stream: char* = fdopen(1, "w")
    fputs("Hello, world!", stream)
    fclose(stream)
    Sleep(5000)
    return 0
