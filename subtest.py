from another_dependency_injector.providing import Container

import cshit
from cshit.analyzer.analyzer import Analyzer
from cshit.parser.parser import Parser
from cshit.symbols.builtin_symbols import builtin_symbols

if __name__ == "__main__":
    container = Container()
    container.value("input_file", "subtest.cs")
    container.value("output_file", "subtest.o")
    container.wire(cshit)

    builtin_symbols.init()

    parser = Parser()

    func = parser.parse_FunctionDefinition_or_FunctionDeclaration()

    analyzer = Analyzer()
    analyzer.analyze_FuncDef(func)

    print(func)