#import "src/std.cs"

fn main() -> int:
    stream: char* = fdopen(1, "w")
    fputs("67", stream)
    fclose(stream)
    Sleep(5000)
    return 0
