from typing import Any, Self

from llvmlite.ir import FloatType, IntType, VoidType

from .interfaces import IAnalyzer, UnresolvedType, TypesMismatch
from ..ast import *
from ..builtin_types import *
from ..stack import StackableObject, Stack
from ..types import PrimitiveType
from ..visitor import ASTVisitor


class Analyzer: ...


class Scope(StackableObject):
    types: list[Type]

    def __init__(self, stack: Stack[Self], analyzer: Analyzer, first: bool = True):
        super().__init__(stack)
        self.analyzer = analyzer
        self.types = []

        builtin_types.init()

        self.int = builtin_types.int_type
        self.char = builtin_types.char_type
        self.float = builtin_types.float_type
        self.void = builtin_types.void_type

        self.register_type(self.int)
        self.register_type(self.char)
        self.register_type(self.float)
        self.register_type(self.void)

    def register_type(self, type: Type):
        assert isinstance(type, Type)
        self.types.append(type)

    def resolve_type_by_name(self, name: IName) -> Type | None:
        for type in self.types:
            if type.test_name(name):
                return type

    def resolve_python_object_type(self, obj: object) -> Type | None:
        typ = type(obj)

        if typ is int:
            return self.int
        elif typ is str:
            return self.char.as_ptr()


class ScopeStack:
    analyzer: Any
    scope: Scope

    def __init__(self, analyzer: Any, scope: Scope):
        self.analyzer = analyzer
        self.scope = scope

    def __enter__(self) -> Self:
        self.analyzer.push_scope(self.scope)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.analyzer.pop_scope()

    def __repr__(self) -> str:
        return self.scope.__repr__()


class Analyzer(IAnalyzer):
    scopes: list[Scope]

    primitives: list[Type]

    def __init__(self):
        self.scopes = [self.create_global_scope()]

    def create_global_scope(self) -> Scope:
        scope = Scope(self, True)
        return scope

    def push_scope(self, scope: Scope):
        self.scopes.append(scope)

    def pop_scope(self):
        self.scopes.pop()

    @property
    def scope(self) -> Scope:
        return self.scopes[-1]

    def analyze(self, ast: AST):
        resolver = TypeResolver(self)
        resolver.visit_recursively(ast)


class TypeResolver(ASTVisitor):
    analyzer: Analyzer

    def __init__(self, analyzer: Analyzer):
        super().__init__()
        self.analyzer = analyzer

    def visit[T:AST](self, ast: T):
        match ast.kind:
            case ASTKind.TypeRef:
                ast: TypeReference = ast
                typ = self.analyzer.scope.resolve_type_by_name(ast.name)
                if typ is None:
                    raise UnresolvedType(ast.name)
                ast.type = typ.as_ptr() if ast.is_ptr else typ
            case ASTKind.ConstExpr:
                ast: ConstExpression = ast
                ast.type = self.analyzer.scope.resolve_python_object_type(ast.value)
