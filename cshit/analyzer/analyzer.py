from another_dependency_injector.wiring import inject, Wire

from .interfaces import IAnalyzer
from ..ast import AST, FileMember, FunctionDefinition, TypeReference, FunctionDeclaration, CodeBlock, VarDeclaration
from ..iname import INameProvider
from ..symbols.builtin_symbols import builtin_symbols
from ..symbols.scope import ScopeStack, Scope
from ..symbols.signature import VariableSignature, TypeSignature
from ..symbols.symbols import *
from ..utils import single_entry


class AnalyzerError(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return f"AnalyzerError: {self.message}"

    def __str__(self) -> str:
        return repr(self)


class UncovertibleTypes(AnalyzerError):
    def __init__(self, a: Type, b: Type):
        super().__init__(f"Type {a} is not convertible to {b}")


class AlreadyDefined(AnalyzerError):
    def __init__(self, name: str, what: str):
        super().__init__(f"{what} {name} already defined in current scope")


class UndefinedSymbol(AnalyzerError):
    def __init__(self, name: str, what: str):
        super().__init__(f"{what} {name} is not defined in current scope")


@inject
class Analyzer(IAnalyzer):
    scopes: ScopeStack
    name_provider: INameProvider

    def __init__(self, name_provider: INameProvider = Wire[INameProvider]):
        self.name_provider = name_provider
        self.scopes = ScopeStack()
        self.scopes.append(Scope(self.scopes))
        for sign, symbol in builtin_symbols.types:
            self.scope.register(sign, symbol, "type")

    def var_sign_from_name(self, name: str) -> VariableSignature:
        return VariableSignature(name)

    def type_sign_from_name(self, name: str) -> TypeSignature:
        return TypeSignature(name)

    @property
    def scope(self) -> Scope:
        return self.scopes.top

    @single_entry()
    def analyze_TypeReference(self, ref: TypeReference) -> Type:
        return self.scope.resolve(self.type_sign_from_name(ref.name.actual()), "type")

    @single_entry()
    def analyze_FuncDef(self, def_: FunctionDefinition) -> Function:
        func = self.analyze_FuncDecl(def_.decl)
        with func.scope.to():
            self.analyze_CodeBlock(def_.code)
        return func

    def analyze_VarDecl(self, decl: VarDeclaration, auto_add: bool = True) -> Variable:
        var = Variable(decl.name.actual(), self.analyze_TypeReference(decl.type))
        if auto_add: self.scope.register(var.signature, var, "var")
        return var

    @single_entry()
    def analyze_FuncDecl(self, decl: FunctionDeclaration, auto_add: bool = True) -> Function:
        ret = self.analyze_TypeReference(decl.ret)
        params: list[Variable] = []
        for param in decl.params:
            params.append(self.analyze_VarDecl(param, auto_add=False))

        func = Function(decl.name.actual(), Type("func").to_function(ret, list(param.type for param in params), decl.var_arg))

        func.scope.set_stack(self.scopes)
        with func.scope.to():
            for param in params:
                func.scope.register(param.signature, param, "var")

        if auto_add:
            self.scope.register(func.signature, func, "func")

        return func

    @single_entry()
    def analyze_CodeBlock(self, code: CodeBlock) -> list[Type] | None:
        pass