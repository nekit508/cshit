import argparse
import sys

from another_dependency_injector.providing import Container

import cshit
from cshit.analyzer.analyzer import Analyzer
from cshit.compiler.compiler import Compiler
from cshit.parser.parser import Parser

if __name__ == "__main__":
    sys.setrecursionlimit(50)

    parser = argparse.ArgumentParser(description="CShit compiler")
    parser.add_argument("input", help="Input file, typically *.cs")
    parser.add_argument("-o", "--output", help="Output file, by default is [input].o")
    args = parser.parse_args()

    if args.input is None:
        print("Wrong program using. Use --help for help.")
        sys.exit(0)

    container = Container()

    container.value("input_file", args.input)
    container.value("output_file", args.input + ".o" if args.output is None else args.output)

    container.wire(cshit)

    import builtins

    original_print = builtins.print
    def custom_print(*args, **kwargs):
        pass
        #original_print(*args, **kwargs)
    builtins.print = custom_print

    parser = Parser()

    print(parser.view)
    ast = parser.parse_File()
    print(ast)

    analyzer = Analyzer()
    analyzer.analyze(ast)

    compiler = Compiler(ast)
    compiler.compile()

    builtins.print = original_print