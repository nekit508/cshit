import enum

from .iname import IName
from .types import Type


class ASTKind(enum.Enum):
    TypeRef = "TypeRef"
    FuncDef = "FuncDef"

    FuncDecl = "FuncDecl"
    VarDecl = "VarDecl"
    VarDef = "VarDef"

    CodeBlock = "CodeBlock"

    ReturnStmt = "ReturnStmt"
    PassStmt = "PassStmt"

    OpExpr = "OpExpr"
    ConstExpr = "ConstExpr"
    CallExpr = "CallExpr"
    IdentExpr = "IdentExpr"
    GetExpr = "GetExpr"
    CastExpr = "CastExpr"

    File = "File"
    Import = "Import"


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


class File(AST):
    members: list[FileMember]

    def __init__(self, members: list[FileMember]):
        self.kind = ASTKind.File
        self.members = members

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"File[{pretty_list(self.members)}]"


class Import(AST):
    name: IName

    def __init__(self,name: IName):
        self.kind = ASTKind.Import
        self.name = name


class Statement(AST):
    pass


class Expression(Statement):
    type: Type


class OpExpression(Expression):
    operator: str
    operands: list[Expression]

    def __init__(self, operator: str, operands: list[Expression]):
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
    type: TypeReference
    expr: Expression

    def __init__(self, typ: TypeReference, expr: Expression):
        self.kind = ASTKind.CastExpr
        self.type = typ
        self.expr = expr

    def __repr__(self) -> str:
        return f"CastExpr<{self.type}>({self.expr})"


class GetExpression(Expression):
    left: Expression
    right: IName

    def __init__(self, left: Expression, right: IName):
        self.kind = ASTKind.GetExpr
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"GetExpr<{self.left}.{self.right}>"


class CallExpression(Expression):
    called: Expression
    params: list[Expression]

    def __init__(self, called: Expression, params: list[Expression]):
        self.kind = ASTKind.ConstExpr
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
        return f"CodeBlock<{pretty_list(self.statements)}>"


class ReturnStatement(Statement):
    expr: Expression

    def __init__(self, expr: Expression):
        self.kind = ASTKind.ReturnStmt
        self.expr = expr

    def __repr__(self) -> str:
        return f"ReturnStmt<{self.expr}>"


class PassStatement(Statement):
    def __init__(self):
        self.kind = ASTKind.PassStmt


class VarDeclaration(FileMember):
    name: IName
    type: TypeReference

    def __init__(self, name: IName, type_ref: TypeReference):
        self.kind = ASTKind.VarDecl
        self.name = name
        self.type = type_ref

    def __repr__(self) -> str:
        return f"{self.name}: {self.type}"

class VarDefinition(FileMember):
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

    def __init__(self, name: IName, ret: TypeReference, params: list[VarDeclaration]):
        self.kind = ASTKind.FuncDecl
        self.name = name
        self.ret = ret
        self.params = params.copy()

    def __repr__(self) -> str:
        return f"fn {self.name} ({" ".join(str(i) for i in self.params)}) -> {self.ret}"


class FunctionDefinition(FileMember):
    decl: FunctionDeclaration
    code: CodeBlock

    def __init__(self, decl: FunctionDeclaration, code: CodeBlock):
        self.kind = ASTKind.FuncDef
        self.decl = decl
        self.code = code

    def __repr__(self) -> str:
        return f"{self.decl}: {self.code}"