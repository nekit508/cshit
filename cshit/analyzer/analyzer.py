from typing import Any, Self, Literal

from another_dependency_injector.wiring import inject, Wire
from llvmlite.ir import FloatType, IntType, VoidType

from .interfaces import IAnalyzer, UnresolvedType, TypesMismatch
from ..ast import *
from ..builtin_types import *
from ..compiler.interfaces import CompileError
from ..iname import INameProvider
from ..lex.token import Token
from ..recursive_dict import RecursiveDict
from ..stack import StackableObject, Stack
from ..types import PrimitiveType, NamedType, Type, StructureType, ContainerType
from ..utils import pretty_list
from ..visitor import ASTVisitor


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


@inject
class Analyzer(IAnalyzer):
    scopes: Stack[Scope]
    func: FunctionType | None
    name_provider: INameProvider
    ref_providers: list[ASTKind]

    def __init__(self, name_provider: INameProvider = Wire[INameProvider]):
        self.name_provider = name_provider
        self.scopes = Stack()
        self.scopes.append(Scope(self.scopes, None))
        self.func = None
        self.ref_providers = [
            ASTKind.IdentExpr,
            ASTKind.GetExpr
        ]
        for name in builtin_types.map:
            if not self.scope.types.register(name, builtin_types.map[name]):
                raise AnalyzerError(f"Second declaration of type with name {name}")

    @property
    def scope(self) -> Scope:
        return self.scopes.top()

    def analyze(self, ast: AST):
        pass
        if ast.kind == ASTKind.File:
            # noinspection PyTypeChecker
            ast: File = ast
            for member in ast.members:
                self.analyze_FileMember(member)
        else: raise AnalyzerError("Expected file")
        pass
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
        else: return self.resolve_target_arithmetic_conversion(a, b)

    def inject_cast_if_needed(self, expr: Expression, target: Type) -> Expression:
        if expr.type != target:
            out = CastExpression("unset via inject", expr)
            out.type = target
            return out
        else: return expr

    def analyze_TypeRef(self, ref: TypeReference):
        if ref.analyzed: return
        else: ref.analyzed = True

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
            case ASTKind.StructDecl:
                # noinspection PyTypeChecker
                self.analyze_StructDecl(member)
            case _:
                raise NotImplementedError(member.kind)

    def analyze_StructDecl(self, struct: StructDeclaration):
        if struct.analyzed: return
        else: struct.analyzed = True

        structure_type = StructureType(struct.name, {}, {})
        self.register_type_unique(struct.name.actual(), structure_type) # register struct existence for correct declarations

        with self.scope.child.w: # we will dump all new symbols in scope, because structure's members accessed via struct type
            for field in struct.fields:
                decl = field if field.kind is ASTKind.VarDecl else field.decl
                self.analyze_VarDecl(decl)
                structure_type.fields[decl.name.actual()] = decl.type
            for method in struct.methods:
                decl = method if method.kind is ASTKind.FuncDecl else method.decl
                name = decl.name.actual()
                decl.name = self.name_provider.simple(struct.name.actual() + "^" + name)
                self.analyze_FuncDecl(decl)
                structure_type.methods[name] = decl.type

        # now all declarations are processed and stored in structure type, we can handle code correctly
        with self.scope.child.w:
            self.register_var("self", structure_type)

            for field in struct.fields:
                if field.kind is ASTKind.VarDef:
                    self.analyze_VarDef(field)
            for field in struct.methods:
                if field.kind is ASTKind.FuncDef:
                    self.analyze_FuncDef(field)

        struct.type = structure_type

    def analyze_FuncDef(self, func_def: FunctionDefinition, add: bool = True):
        if func_def.analyzed: return
        else: func_def.analyzed = True

        self.analyze_FuncDecl(func_def.decl, add)

        with self.scope.child.w:
            for param in func_def.decl.params:
                self.register_var_unique(param.name.actual(), param.type)
            self.func = func_def.decl.type
            self.analyze_CodeBlock(func_def.code)

    def analyze_FuncDecl(self, decl: FunctionDeclaration, add: bool = True):
        if decl.analyzed: return
        else: decl.analyzed = True

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
        if var_def.analyzed: return
        else: var_def.analyzed = True

        self.analyze_VarDecl(var_def.decl, add)
        if var_def.initial_value is not None:
            self.analyze_Expression(var_def.initial_value)
            if not self.is_convertible(var_def.initial_value.type, var_def.decl.type):
                raise UncovertibleTypes(var_def.initial_value.type, var_def.decl.type)

    def analyze_VarDecl(self, decl: VarDeclaration, add: bool = True):
        if decl.analyzed: return
        else: decl.analyzed = True

        if hasattr(decl, "type"): return

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
            case ASTKind.GetExpr:
                # noinspection PyTypeChecker
                self.analyze_GetExpr(expr)
            case _: raise NotImplementedError(expr.kind)
        
    def analyze_GetExpr(self, get: GetExpression):
        if get.analyzed: return
        else: get.analyzed = True


        self.analyze_Expression(get.left)

        if not isinstance(get.left.type, ContainerType):
            raise AnalyzerError(f"Type {get.left.type} is not a container type")

        name = get.right.actual()
        accessed = get.left.type.get_member(name)
        if accessed is None:
            raise UndefinedSymbol(name, f"{get.left.type} member")

        get.type = accessed


    def analyze_OpExpr(self, op: OpExpression):
        if op.analyzed: return
        else: op.analyzed = True

        if len(op.operands) == 2:
            for operand in op.operands:
                self.analyze_Expression(operand)

            operator = op.operator
            left, right = op.operands

            if operator is TokenType.EQ:
                if op.operands[0].kind not in self.ref_providers: raise AnalyzerError(f"Left operand of \"=\" must one of {pretty_list(self.ref_providers)}")
                if left.type.is_func:
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
                operand: Expression = op.operands[0]
                if operand.kind is not ASTKind.IdentExpr:
                    raise AnalyzerError("Can take address only of named variable")
                # noinspection PyTypeChecker
                operand: IdentExpression = operand
                self.analyze_IdentExpr(operand, (True, True, False))
                op.type = op.operands_type = operand.type.as_ptr()
            else: raise AnalyzerError(f"Unknown unary operator type {op.operator}")
        else:raise NotImplementedError("Non binary/unary operators")

    def analyze_ConstExpr(self, const: ConstExpression):
        if const.analyzed: return
        else: const.analyzed = True

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

    def analyze_IdentExpr(self, ident: IdentExpression, required: tuple[bool, bool, bool] = (True, True, False)):
        if ident.analyzed: return
        else: ident.analyzed = True

        var, func, typ = required
        name = ident.name.actual()

        out = None
        if var:
            out = self.scope.variables.resolve(name)
        if func and out is None:
            out = self.scope.functions.resolve(name)
        if typ and out is None:
            out = self.scope.types.resolve(name)
        if out is None: raise UndefinedSymbol(name, f"Symbol (searched in (variables, functions, types) {required})")
        ident.type = out

    def analyze_CallExpr(self, call: CallExpression):
        if call.analyzed: return
        else: call.analyzed = True

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
        if block.analyzed: return
        else: block.analyzed = True

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
            case ASTKind.WhileStmt:
                # noinspection PyTypeChecker
                self.analyze_WhileStmt(stmt)
            case _:
                try:
                    # noinspection PyTypeChecker
                    self.analyze_Expression(stmt)
                except Exception as e:
                    raise AnalyzerError(f"{e}")

    def analyze_IfStmt(self, stmt: IfStatement):
        if stmt.analyzed: return
        else: stmt.analyzed = True

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

    def analyze_WhileStmt(self, stmt: WhileStatement):
        if stmt.analyzed: return
        else: stmt.analyzed = True

        if stmt.do_while:
            with self.scope.child.w:
                self.analyze_CodeBlock(stmt.body)

            self.analyze_Expression(stmt.condition)
            if not self.is_convertible(stmt.condition.type, builtin_types.bool_type):
                raise UncovertibleTypes(stmt.condition.type, builtin_types.bool_type)

            if stmt.end is not None:
                with self.scope.child.w:
                    self.analyze_CodeBlock(stmt.end)
        else:
            self.analyze_Expression(stmt.condition)
            if not self.is_convertible(stmt.condition.type, builtin_types.bool_type):
                raise UncovertibleTypes(stmt.condition.type, builtin_types.bool_type)

            with self.scope.child.w:
                self.analyze_CodeBlock(stmt.body)

            if stmt.end is not None:
                with self.scope.child.w:
                    self.analyze_CodeBlock(stmt.end)

    def analyze_ReturnStmt(self, ret: ReturnStatement):
        if ret.analyzed: return
        else: ret.analyzed = True

        if self.func is None:
            raise AnalyzerError("Return not in function body")

        if ret.expr is not None:
            self.analyze_Expression(ret.expr)
            ret.type = ret.expr.type
        else: ret.type = builtin_types.void_type

        if not self.is_convertible(ret.type, self.func.ret):
            raise UncovertibleTypes(ret.type, self.func.ret)