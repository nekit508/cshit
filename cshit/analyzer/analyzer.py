from typing import Any, Self, Literal

from llvmlite.ir import FloatType, IntType, VoidType

from .interfaces import IAnalyzer, UnresolvedType, TypesMismatch
from ..ast import *
from ..builtin_types import *
from ..compiler.interfaces import CompileError
from ..lex.token import Token
from ..recursive_dict import RecursiveDict
from ..stack import StackableObject, Stack
from ..types import PrimitiveType, NamedType, Type
from ..visitor import ASTVisitor


class AnalyzerError(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return f"AnalyzerError: {self.message}"


class UncovertibleTypes(AnalyzerError):
    def __init__(self, a: Type, b: Type):
        super().__init__(f"Type {a} is not convertible to {b}")


class AlreadyDefined(AnalyzerError):
    def __init__(self, name: str, what: str):
        super().__init__(f"{what} {name} already defined in current scope")


class UndefinedSymbol(AnalyzerError):
    def __init__(self, name: str, what: str):
        super().__init__(f"{what} {name} is not defined in current scope")


class Scope(StackableObject):
    variables: RecursiveDict[Type]
    functions: RecursiveDict[Type]
    types: RecursiveDict[Type]

    parent: Self | None

    def __init__(self, stack: Stack[Self], parent: Self | None):
        super().__init__(stack)

        self.parent = parent

        self.variables = RecursiveDict(self.parent and self.parent.variables)
        self.functions = RecursiveDict(self.parent and self.parent.functions)
        self.types = RecursiveDict(self.parent and self.parent.types)

    @property
    def child(self) -> Self:
        return Scope(self.stack, self)

    @property
    def w(self):
        return self.to()


class Analyzer(IAnalyzer):
    scopes: Stack[Scope]
    func: FunctionType | None

    def __init__(self):
        self.scopes = Stack()
        self.scopes.append(Scope(self.scopes, None))
        self.func = None
        for name in builtin_types.map: # add builtin type to analyzer indexing
            if not self.scope.types.register(name, builtin_types.map[name]):
                raise AnalyzerError(f"Second declaration of type with name {name}")

    @property
    def scope(self) -> Scope:
        return self.scopes.top()

    def analyze(self, ast: AST):
        if ast.kind == ASTKind.File:
            # noinspection PyTypeChecker
            ast: File = ast
            for member in ast.members:
                self.analyze_FileMember(member)
        else: raise AnalyzerError("Expected file")
        #breakpoint()

    def register_var(self, name: str, typ: Type):
        self.scope.variables[name] = typ

    def register_var_unique(self, name: str, typ: Type):
        if not self.scope.variables.register(name, typ):
            raise AlreadyDefined(name, "Variable")

    def register_func(self, name: str, typ: FunctionType):
        self.scope.functions[name] = typ

    def register_func_unique(self, name: str, typ: FunctionType):
        if not self.scope.functions.register(name, typ):
            raise AlreadyDefined(name, "Function")

    def register_type(self, name: str, typ: Type):
        self.scope.types[name] = typ

    def register_type_unique(self, name: str, typ: Type):
        if not self.scope.types.register(name, typ):
            raise AlreadyDefined(name, "Type")

    def is_convertible(self, a: Type, b: Type) -> bool:
        """ a -> b """
        if b.is_ptr and a in builtin_types.integers:
            return True
        return a == b

    def resolve_target_arithmetic_conversion(self, a: Type, b: Type) -> Type:
        if a not in builtin_types.ranks:
            raise AnalyzerError(f"{a} is not an arithmetic type")
        if b not in builtin_types.ranks:
            raise AnalyzerError(f"{b} is not an arithmetic type")

        return a if builtin_types.ranks[a] >= builtin_types.ranks[b] else b

    def resolve_target_logic_conversion(self, a: Type, b: Type) -> Type:
        if a.is_ptr or b.is_ptr:
            return builtin_types.ptr_type
        else: self.resolve_target_arithmetic_conversion(a, b)

    def inject_cast_if_needed(self, expr: Expression, target: Type) -> Expression:
        if expr.type != target:
            out = CastExpression("unset via inject", expr)
            out.type = target
            return out
        else: return expr

    def analyze_TypeRef(self, ref: TypeReference):
        ref.type = self.scope.types[ref.name.actual()]
        if ref.type is None: raise UndefinedSymbol(ref.name.actual(), "Type")
        if ref.is_ptr: ref.type = ref.type.as_ptr()

    def analyze_FileMember(self, member: FileMember):
        match member.kind:
            case ASTKind.FuncDecl:
                # noinspection PyTypeChecker
                self.analyze_FuncDecl(member)
            case ASTKind.FuncDef:
                # noinspection PyTypeChecker
                self.analyze_FuncDef(member)
            case ASTKind.VarDecl:
                # noinspection PyTypeChecker
                self.analyze_VarDecl(member)
            case ASTKind.VarDef:
                # noinspection PyTypeChecker
                self.analyze_VarDef(member)

    def analyze_FuncDef(self, func_def: FunctionDefinition, add: bool = True):
        self.analyze_FuncDecl(func_def.decl, add)

        with self.scope.child.w:
            for param in func_def.decl.params:
                self.register_var_unique(param.name.actual(), param.type)
            self.func = func_def.decl.type
            self.analyze_CodeBlock(func_def.code)

    def analyze_FuncDecl(self, decl: FunctionDeclaration, add: bool = True):
        self.analyze_TypeRef(decl.ret)
        for param in decl.params:
            self.analyze_VarDecl(param, False)

        decl.type = FunctionType(
            decl.name,
            decl.ret.type,
            list(param.type for param in decl.params),
            decl.var_arg
        )

        if add: self.register_func_unique(decl.name.actual(), decl.type)

    def analyze_VarDef(self, var_def: VarDefinition, add: bool = True):
        self.analyze_VarDecl(var_def.decl, add)
        if var_def.initial_value is not None:
            self.analyze_Expression(var_def.initial_value)
            if not self.is_convertible(var_def.initial_value.type, var_def.decl.type):
                raise UncovertibleTypes(var_def.initial_value.type, var_def.decl.type)

    def analyze_VarDecl(self, decl: VarDeclaration, add: bool = True):
        self.analyze_TypeRef(decl.type_ref)
        decl.type = decl.type_ref.type

        if add:
            if decl.name is not None:
                self.register_var(decl.name.actual(), decl.type)
            else: raise AnalyzerError(f"Var {decl} must be named")

    def analyze_Expression(self, expr: Expression):
        match expr.kind:
            case ASTKind.CallExpr:
                # noinspection PyTypeChecker
                self.analyze_CallExpr(expr)
            case ASTKind.IdentExpr:
                # noinspection PyTypeChecker
                self.analyze_IdentExpr(expr)
            case ASTKind.ConstExpr:
                # noinspection PyTypeChecker
                self.analyze_ConstExpr(expr)
            case ASTKind.OpExpr:
                # noinspection PyTypeChecker
                self.analyze_OpExpr(expr)
            case _: raise NotImplementedError(expr.kind)

    def analyze_OpExpr(self, op: OpExpression):
        if len(op.operands) == 2:
            for operand in op.operands:
                self.analyze_Expression(operand)

            operator = op.operator
            left, right = op.operands

            if operator is TokenType.EQ:
                if op.operands[0].kind is not ASTKind.IdentExpr: raise AnalyzerError(f"Left operand of = op must be ident but {op.operands[0].kind}")
                if left.type.is_func: # TODO reject be final/variable
                    raise AnalyzerError("Cannot set function")

                op.type = left.type
                op.operands[1] = self.inject_cast_if_needed(right, left.type)
            elif operator in builtin_types.arithmetic_binary_operators:
                op.type = op.operands_type = self.resolve_target_arithmetic_conversion(left.type, right.type)
                op.operands = list(self.inject_cast_if_needed(operand, op.type) for operand in op.operands)
            elif operator in builtin_types.logic_binary_operators:
                op.operands_type = self.resolve_target_logic_conversion(left.type, right.type)
                op.operands = list(self.inject_cast_if_needed(operand, op.operands_type) for operand in op.operands)
                op.type = builtin_types.bool_type
            else: raise AnalyzerError(f"Unknown binary operator type {operator}")
        elif len(op.operands) == 1:
            if op.operator is TokenType.AMPERSAND:
                operand = op.operands[0]
                if operand.kind is not ASTKind.IdentExpr:
                    raise AnalyzerError("Can take address only of named variable")
                self.analyze_IdentExpr(operand, (True, True, False))
                op.type = op.operands_type = operand.type.as_ptr()
            else: raise AnalyzerError(f"Unknown unary operator type {op.operator}")
        else:raise NotImplementedError("Non binary/unary operators")

    def analyze_ConstExpr(self, const: ConstExpression):
        typ = type(const.value)

        if typ is int:
            const.type = builtin_types.int_type
        elif typ is float:
            const.type = builtin_types.float_type
        elif typ is bool:
            const.type = builtin_types.bool_type
        elif typ is str:
            const.type = builtin_types.char_type.as_ptr()
        else: AnalyzerError(f"Value {const} has wrong type {typ}")

    def analyze_IdentExpr(self, ident: IdentExpression, required: tuple[bool, bool, bool] = (True, True, True)): # 1) var 2) func 3) type
        var, func, typ = required
        name = ident.name.actual()

        out = None
        if var:
            out = self.scope.variables.resolve(name)
        if func and out is None:
            out = self.scope.functions.resolve(name)
        if typ and out is None:
            out = self.scope.types.resolve(name)
        if out is None: raise UndefinedSymbol(name, "Symbol")
        ident.type = out

    def analyze_CallExpr(self, call: CallExpression):
        self.analyze_Expression(call.called)

        typ = call.called.type
        if not isinstance(typ, FunctionType): raise AnalyzerError(f"Called non callable value {call.called}")
        call.type = typ.ret

        if len(typ.params) != len(call.params) and (not typ.var_arg or len(typ.params) > len(call.params)):
            raise CompileError(f"Wrong len of params of function {typ} expected {len(typ.params)}{"+" if typ.var_arg else ""} got {len(call.params)}")

        for i in range(len(call.params)):
            param = call.params[i]
            self.analyze_Expression(param)

            if i < len(typ.params) and not self.is_convertible(param.type, typ.params[i]):
                raise UncovertibleTypes(param.type, typ.params[i])

    def analyze_CodeBlock(self, block: CodeBlock):
        for statement in block.statements:
            self.analyze_Statement(statement)

    def analyze_Statement(self, stmt: Statement):
        match stmt.kind:
            case ASTKind.VarDecl:
                # noinspection PyTypeChecker
                self.analyze_VarDecl(stmt)
            case ASTKind.VarDef:
                # noinspection PyTypeChecker
                self.analyze_VarDef(stmt)
            case ASTKind.ReturnStmt:
                # noinspection PyTypeChecker
                self.analyze_ReturnStmt(stmt)
            case ASTKind.IfStmt:
                # noinspection PyTypeChecker
                self.analyze_IfStmt(stmt)
            case _:
                # noinspection PyTypeChecker
                self.analyze_Expression(stmt)

    def analyze_IfStmt(self, stmt: IfStatement):
        for condition in stmt.conditions:
            self.analyze_Expression(condition)
            if not self.is_convertible(condition.type, builtin_types.bool_type):
                raise UncovertibleTypes(condition.type, builtin_types.bool_type)

        for branch in stmt.branches:
            with self.scope.child.w:
                self.analyze_CodeBlock(branch)

        if stmt.else_block is not None:
            with self.scope.child.w:
                self.analyze_CodeBlock(stmt.else_block)

    def analyze_ReturnStmt(self, ret: ReturnStatement):
        self.analyze_Expression(ret.expr)
        ret.type = ret.expr.type

        if self.func is None:
            raise AnalyzerError("Return out of function body")
        if not self.is_convertible(ret.type, self.func.ret):
            raise UncovertibleTypes(ret.type, self.func.ret)