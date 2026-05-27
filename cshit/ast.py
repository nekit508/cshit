import enum
from collections.abc import Callable

from .builtin_types import builtin_types
from .iname import IName
from .lex.interfaces import TokenType
from .types import Type, FunctionType


class Operator:
    strategy: Callable[[Type, ...], Type]

    def __init__(self, strategy: Callable[[Type, ...], Type]):
        self.strategy = strategy

    def result_type(self, *operands: Type) -> Type:
        return self.strategy(*operands)


class ASTKind(enum.Enum):
    TypeRef = "TypeRef"
    FuncDef = "FuncDef"

    FuncDecl = "FuncDecl"
    VarDecl = "VarDecl"
    VarDef = "VarDef"

    CodeBlock = "CodeBlock"

    ReturnStmt = "ReturnStmt"
    PassStmt = "PassStmt"
    IfStmt = "IfStmt"

    OpExpr = "OpExpr"
    ConstExpr = "ConstExpr"
    CallExpr = "CallExpr"
    IdentExpr = "IdentExpr"
    GetExpr = "GetExpr"
    CastExpr = "CastExpr"

    ImportDir = "ImportDir"

    File = "File"


class AST:
    kind: ASTKind


class TypeReference(AST):
    name: IName
    is_ptr: bool

    type: Type

    def __init__(self, name: IName, is_ptr: bool):
        self.kind = ASTKind.TypeRef
        self.name = name
        self.is_ptr = is_ptr

    def __repr__(self) -> str:
        return f"type<{self.name}{"*" if self.is_ptr else ""}>"


class FileMember(AST):
    pass


class Directive(FileMember):
    pass


class ImportDirective(Directive):
    file: str

    def __init__(self, file: str):
        self.kind = ASTKind.ImportDir
        self.file = file

    def __repr__(self) -> str:
        return f"#import {self.file}"


class File(AST):
    members: list[FileMember]

    def __init__(self, members: list[FileMember]):
        self.kind = ASTKind.File
        self.members = members

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"File[{pretty_list(self.members)}]"


class Statement(AST):
    pass


class Expression(Statement):
    type: Type


class OpExpression(Expression):
    operator: TokenType
    operands: list[Expression]

    operands_type: Type

    def __init__(self, operator: TokenType, operands: list[Expression]):
        self.kind = ASTKind.OpExpr
        self.operator = operator
        self.operands = operands

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"Op<{self.operator}>[{pretty_list(self.operands)}]"

class ConstExpression(Expression):
    value: object

    def __init__(self, value: object):
        self.kind = ASTKind.ConstExpr
        self.value = value

    def __repr__(self) -> str:
        return f"Const<{self.value}>"


class IdentExpression(Expression):
    name: IName

    def __init__(self, name: IName):
        self.kind = ASTKind.IdentExpr
        self.name = name

    def __repr__(self) -> str:
        return f"IdentExpr<{self.name}>"


class CastExpression(Expression):
    type_ref: TypeReference
    expr: Expression

    def __init__(self, typ: TypeReference, expr: Expression):
        self.kind = ASTKind.CastExpr
        self.type_ref = typ
        self.expr = expr

    def __repr__(self) -> str:
        return f"CastExpr<{self.type_ref}>({self.expr})"


class GetExpression(Expression):
    left: Expression
    right: IName
    static: bool

    def __init__(self, left: Expression, right: IName, static: bool):
        self.kind = ASTKind.GetExpr
        self.left = left
        self.right = right
        self.static = static

    def __repr__(self) -> str:
        return f"GetExpr<{self.left}{"::" if self.static else "."}{self.right}>"


class CallExpression(Expression):
    called: Expression
    params: list[Expression]

    def __init__(self, called: Expression, params: list[Expression]):
        self.kind = ASTKind.CallExpr
        self.called = called
        self.params = params

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"CallExpr<{self.called}>[{pretty_list(self.params)}]"


class CodeBlock(Statement):
    statements: list[Statement]

    def __init__(self, statements: list[Statement]):
        self.kind = ASTKind.CodeBlock
        self.statements = statements

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"CodeBlock[{pretty_list(self.statements)}]"


class ReturnStatement(Statement):
    expr: Expression | None
    type: Type

    def __init__(self, expr: Expression | None):
        self.kind = ASTKind.ReturnStmt
        self.expr = expr

    def __repr__(self) -> str:
        return f"ReturnStmt<{self.expr}>"


class PassStatement(Statement):
    def __init__(self):
        self.kind = ASTKind.PassStmt


class IfStatement(Statement):
    conditions: list[Expression]
    branches: list[CodeBlock]
    else_block: CodeBlock

    def __init__(self, conditions: list[Expression], branches: list[CodeBlock], negative: CodeBlock):
        self.kind = ASTKind.IfStmt
        self.conditions = conditions
        self.branches = branches
        self.else_block = negative

    def __repr__(self) -> str:
        from cshit.utils import pretty_list
        return f"IfStmt<{pretty_list(list(f"{self.conditions[i]} -> {self.branches[i]}" for i in range(len(self.branches))), sep="; ")}{f" else: {self.else_block}" if self.else_block is not None else ""}>"


class VarDeclaration(FileMember, Statement):
    name: IName | None
    type_ref: TypeReference

    type: Type

    def __init__(self, name: IName | None, type_ref: TypeReference):
        self.kind = ASTKind.VarDecl
        self.name = name
        self.type_ref = type_ref

    def __repr__(self) -> str:
        return f"{self.name if self.name is not None else "<NA>"} {self.type_ref}"

class VarDefinition(FileMember, Statement):
    decl: VarDeclaration
    initial_value: Expression

    def __init__(self, decl: VarDeclaration, initial_value: Expression):
        self.decl = decl
        self.kind = ASTKind.VarDef
        self.initial_value = initial_value

    def __repr__(self) -> str:
        return f"{self.decl} = {self.initial_value}"


class FunctionDeclaration(FileMember):
    name: IName
    ret: TypeReference
    params: list[VarDeclaration]
    var_arg: bool

    type: FunctionType

    def __init__(self, name: IName, ret: TypeReference, params: list[VarDeclaration], var_arg: bool):
        self.kind = ASTKind.FuncDecl
        self.name = name
        self.ret = ret
        self.params = params.copy()
        self.var_arg = var_arg

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"fn {self.name} ({pretty_list(self.params)}{f", ..." if self.var_arg else ""}) -> {self.ret}"


class FunctionDefinition(FileMember):
    decl: FunctionDeclaration
    code: CodeBlock

    def __init__(self, decl: FunctionDeclaration, code: CodeBlock):
        self.kind = ASTKind.FuncDef
        self.decl = decl
        self.code = code

    def __repr__(self) -> str:
        return f"{self.decl}: {self.code}"