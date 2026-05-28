from typing import Self, Any

from another_dependency_injector.wiring import inject, Wire
from llvmlite import ir, binding
from llvmlite.binding import ModuleRef, PipelineTuningOptions
from llvmlite.ir import Function, CallInstr, Value, NamedValue

from .interfaces import ICompiler, CompileError
from ..ast import FunctionDefinition, ASTKind, FunctionDeclaration, CodeBlock, Expression, \
    ConstExpression, File, FileMember, VarDeclaration, VarDefinition, CastExpression, CallExpression, Statement, \
    IdentExpression, ReturnStatement, IfStatement, OpExpression, Operator, WhileStatement, StructDeclaration, \
    GetExpression
from ..builtin_types import builtin_types
from ..lex.interfaces import TokenType
from ..recursive_dict import RecursiveDict
from ..stack import StackableObject, Stack
from ..types import PtrType, Type


class UnresolvedSymbol(Exception):
    name: str
    type: str

    def __init__(self, name: str, typ: str):
        self.name = name
        self.type = typ

    def __repr__(self) -> str:
        return f"Unknown symbol {self.name} of type {self.type}"

    def __str__(self) -> str:
        return f"{self.__repr__()}"


class NameProvider:
    def get_name(self, obj: Any) -> str:
        raise NotImplementedError()


class RandomNameProvider(NameProvider):
    last_id: int

    def __init__(self):
        self.last_id = -1

    def get_name(self, obj: Any) -> str:
        self.last_id += 1
        return f"random_name_{self.last_id}"


class Context(StackableObject):
    variables: RecursiveDict[NamedValue]
    functions: RecursiveDict[NamedValue]
    parent: Self | None

    def __init__(self, stack: Stack[Self], parent: Self | None = None):
        super().__init__(stack)
        self.functions = RecursiveDict(parent and parent.functions)
        self.variables = RecursiveDict(parent and parent.variables)
        self.parent = parent

    def register_variable(self, var: NamedValue, name: str | None = None) -> bool:
        return self.variables.register(name or var.name, var)

    def resolve_variable(self, name: str) -> NamedValue | None:
        return self.variables[name]

    def register_function(self, func: Function, name: str | None = None) -> tuple[bool, bool]:
        """ :returns (var, func) """
        return self.register_variable(func, name), self.functions.register(name or func.name, func)

    def resolve_function(self, name: str) -> Function | None:
        return self.functions[name]

    @property
    def child(self):
        return Context(self.stack, self).to()

    def handle(self, obj: Self, data: tuple[Any, ...]):
        print(f"exit with {self.functions.data}")

    #def __repr__(self) -> str:
    #    print(f"Context[functions:{self.functions}; variables:{self.variables}] <- {self.parent}")

class CIRBuilder(ir.IRBuilder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def access_value(self, val: ir.Value) -> ir.NamedValue:
        return val if isinstance(val, ir.Argument) or isinstance(val, ir.ReturnValue) else self.load(val)


class Builder(StackableObject):
    builder: CIRBuilder

    def __init__(self, stack: Stack[Self], block: ir.Block | None = None, dummy: bool = False):
        super().__init__(stack)
        self.builder = None if dummy else CIRBuilder(block=block)

    def child(self, block: ir.Block | None = None):
        return Builder(self.stack, block).to()

    @property
    def anonymous(self):
        return self.child(None)


class Compiler(ICompiler):
    ast: File
    module: ir.Module
    output: str
    context_stack: Stack[Context]
    builder_stack: Stack[Builder]
    name_provider: NameProvider
    operators_type_resolvers: dict[TokenType, Operator]
    logic_operators_map: dict[TokenType, str]

    @inject
    def __init__(self, ast: File, source: str = Wire["input_file"], output: str = Wire["output_file"]):
        self.ast = ast
        self.output = output

        self.name_provider = RandomNameProvider()

        self.init_llvm()
        self.module = ir.Module(name=source)

        self.context_stack = Stack()
        self.context_stack.append(Context(self.context_stack))

        self.builder_stack = Stack()
        self.builder_stack.append(Builder(self.builder_stack, dummy=True))

        self.logic_operators_map = {
            TokenType.EQEQ: "==",
            TokenType.NEQ: "!=",
            TokenType.GT: ">",
            TokenType.GE: ">=",
            TokenType.LT: "<",
            TokenType.LE: "<="
        }

    @property
    def random_name(self) -> str:
        return self.name_provider.get_name(None)

    @property
    def context(self) -> Context:
        return self.context_stack[-1]

    @property
    def builder(self) -> Builder:
        return self.builder_stack[-1]

    @property
    def ir_builder(self) -> CIRBuilder:
        return self.builder.builder

    def init_llvm(self):
        binding.initialize_native_target()
        binding.initialize_native_asmprinter()

    def compile_text(self, text: str):
        print("=================================   Raw IR Code   =================================")
        print(text)
        mod = binding.parse_assembly(text)
        mod.verify()

        self.compile_module_ref(mod)

    def compile(self):
        self.compile_File(self.ast)

        print("=================================   Raw IR Code   =================================")
        print(self.module)
        mod = binding.parse_assembly(str(self.module))
        mod.verify()

        self.compile_module_ref(mod)

    def compile_module_ref(self, mod: ModuleRef):
        target = binding.Target.from_default_triple()
        target_machine = target.create_target_machine(codemodel="default")

        #pass_manager_builder = binding.create_pass_builder(target_machine, PipelineTuningOptions())
        #pass_manager = pass_manager_builder.getModulePassManager()
        #pass_manager.run(mod, pass_manager_builder)

        print("=================================   Resulting IR Code   =================================")
        print(mod)

        obj_code = target_machine.emit_object(mod)
        with open(self.output, "wb") as f:
            f.write(obj_code)

    def require_var(self, name: str) -> NamedValue:
        out = self.context.resolve_variable(name)
        if out is None:
            raise UnresolvedSymbol(name, "var")
        else: return out

    def require_func(self, name: str) -> Function:
        out = self.context.resolve_function(name)
        if out is None:
            raise UnresolvedSymbol(name, "func")
        else: return out

    def compile_cast(self, a: ir.Value, a_type: Type, target_type: Type) -> ir.Value:
        pass

    def compile_File(self, file: File):
        for member in file.members:
            self.compile_FileMember(member)

    def compile_FileMember(self, file_member: FileMember):
        if file_member.kind is ASTKind.VarDecl:
            # noinspection PyTypeChecker
            self.compile_GlobalVarDecl(file_member)
        elif file_member.kind is ASTKind.VarDef:
            # noinspection PyTypeChecker
            self.compile_GlobalVarDef(file_member)
        elif file_member.kind is ASTKind.FuncDecl:
            # noinspection PyTypeChecker
            self.compile_FuncDecl(file_member)
        elif file_member.kind is ASTKind.FuncDef:
            # noinspection PyTypeChecker
            self.compile_FuncDef(file_member)
        elif file_member.kind is ASTKind.StructDecl:
            # noinspection PyTypeChecker
            self.compile_StructDecl(file_member)
        else: raise NotImplementedError(file_member.kind)

    def compile_StructDecl(self, struct: StructDeclaration) -> ir.IdentifiedStructType:
        native_type = self.module.context.get_identified_type(struct.name.actual())
        analyzed_type = struct.type

        body: list[Type | None] = [None] * len(analyzed_type.fields_idx)
        for name in analyzed_type.fields_idx:
            body[analyzed_type.fields_idx[name]] = analyzed_type.fields[name]

        native_type.set_body(body)

        with self.context.child:
            for member in struct.methods:
                if member.kind is ASTKind.FuncDecl:
                    self.compile_FuncDecl(member)
                else: self.compile_FuncDef(member)

        return native_type

    def compile_FuncDecl(self, decl: FunctionDeclaration) -> ir.Function:
        name = decl.name.actual()
        out = ir.Function(self.module,
                          ir.FunctionType(decl.ret.type.as_native(),
                                          list(param.type_ref.type.as_native() for param in decl.params)),
                          name = name)
        var, func = self.context.register_function(out)
        if not func:
            raise CompileError(f"Cannot create function with name {name}, because var with same name already exists in this scope.")
        elif not var:
            raise CompileError(f"Cannot create function with name {name}, because func with same name already exists in this scope.")
        return out

    def compile_ReturnStmt(self, stmt: ReturnStatement):
        if stmt.type == builtin_types.void_type:
            self.ir_builder.ret_void()
        else: self.ir_builder.ret(self.compile_Expression(stmt.expr))

    def compile_FuncDef(self, func_def: FunctionDefinition) -> ir.Function:
        out = self.compile_FuncDecl(func_def.decl)
        with self.context.child, self.builder.child(out.append_basic_block(self.random_name)):
            for i in range(len(func_def.decl.params)):
                self.context.register_variable(out.args[i], func_def.decl.params[i].name.actual())
            self.compile_CodeBlock(func_def.code)
        return out

    def compile_CodeBlock(self, block: CodeBlock):
        for stmt in block.statements:
            self.compile_Statement(stmt)

    # noinspection PyTypeChecker
    def compile_Statement(self, stmt: Statement):
        print("compile_Statement", stmt)
        if stmt.kind is ASTKind.ReturnStmt:
            return self.compile_ReturnStmt(stmt)
        elif stmt.kind is ASTKind.VarDef:
            return self.compile_VarDef(stmt)
        elif stmt.kind is ASTKind.VarDecl:
            return self.compile_VarDecl(stmt)
        elif stmt.kind is ASTKind.IfStmt:
            return self.compile_IfStmt(stmt)
        elif stmt.kind is ASTKind.WhileStmt:
            return self.compile_WhileStmt(stmt)
        elif isinstance(stmt, Expression): # not any statement resolved - maybe it is Expression
            return self.compile_Expression(stmt)

        raise CompileError(f"Unknown statement {stmt} with kind {stmt.kind}")

    def compile_WhileStmt(self, stmt: WhileStatement):
        if stmt.do_while:
            body_start = self.ir_builder.append_basic_block(self.random_name)
            condition_start = self.ir_builder.append_basic_block(self.random_name)
            merge = self.ir_builder.append_basic_block(self.random_name)

            self.ir_builder.branch(body_start)

            self.ir_builder.position_at_start(body_start)
            self.compile_CodeBlock(stmt.body)
            self.ir_builder.branch(condition_start)

            self.ir_builder.position_at_start(condition_start)
            self.ir_builder.cbranch(self.compile_Expression(stmt.condition), body_start, merge)

            self.ir_builder.position_at_start(merge)
            if stmt.end is not None:
                self.compile_CodeBlock(stmt.end)
        else:
            condition_start = self.ir_builder.append_basic_block(self.random_name)
            merge = self.ir_builder.append_basic_block(self.random_name)
            body_start = self.ir_builder.append_basic_block(self.random_name)

            self.ir_builder.branch(condition_start)

            self.ir_builder.position_at_start(condition_start)
            self.ir_builder.cbranch(self.compile_Expression(stmt.condition), body_start, merge)

            self.ir_builder.position_at_start(body_start)
            self.compile_CodeBlock(stmt.body)
            self.ir_builder.branch(condition_start)

            self.ir_builder.position_at_start(merge)
            if stmt.end is not None:
                self.compile_CodeBlock(stmt.end)

    def compile_IfStmt(self, stmt: IfStatement):
        branches_starts: list[ir.Branch] = []
        conditions_starts: list[ir.Branch] = []

        for i in range(len(stmt.branches)):
            if i != 0: conditions_starts.append(self.ir_builder.append_basic_block(self.random_name))
            branches_starts.append(self.ir_builder.append_basic_block(self.random_name))

        if stmt.else_block is not None:
            branches_starts.append(self.ir_builder.append_basic_block(self.random_name))

        merge = self.ir_builder.append_basic_block(self.random_name)

        for i in range(len(stmt.branches)):
            # compile expression and cbranch
            if i != 0: self.ir_builder.position_at_start(conditions_starts[i-1])
            self.ir_builder.cbranch(self.compile_Expression(stmt.conditions[i]), branches_starts[i],
                                    conditions_starts[i]
                                    if i != len(stmt.branches)-1 else
                                    (merge if stmt.else_block is None else branches_starts[-1])) # last one jumps into else block instead of not existing next elif

            # compile current branch
            self.ir_builder.position_at_start(branches_starts[i])
            self.compile_CodeBlock(stmt.branches[i])
            if self.ir_builder.block.is_terminated: continue # we returned from function or etc
            self.ir_builder.branch(merge)

        if stmt.else_block is not None:
            self.ir_builder.position_at_start(branches_starts[-1])
            self.compile_CodeBlock(stmt.else_block)
            self.ir_builder.branch(merge)

        self.ir_builder.position_at_start(merge)

    def compile_VarDecl(self, var_decl: VarDeclaration) -> ir.instructions.AllocaInstr:
        print("compile_VarDecl", var_decl.type_ref.type.as_native(), "name:" , var_decl.name)
        out = self.ir_builder.alloca(var_decl.type_ref.type.as_native(), name=var_decl.name.actual())
        self.context.register_variable(out)
        return out

    def compile_VarDef(self, var_def: VarDefinition) -> ir.Value:
        value = self.compile_VarDecl(var_def.decl)
        self.ir_builder.store(self.compile_Expression(var_def.initial_value), value)
        return value

    def compile_GlobalVarDecl(self, var_decl: VarDeclaration) -> ir.GlobalVariable:
        print("compile_GlobalVarDecl", var_decl.type_ref.type.as_native(), "name:" , var_decl.name)
        out = ir.GlobalVariable(self.module, var_decl.type_ref.type.as_native(), var_decl.name.actual())
        self.context.register_variable(out)
        return out

    def compile_GlobalVarDef(self, var_def: VarDefinition) -> ir.Value:
        value = self.compile_GlobalVarDecl(var_def.decl)
        value.initializer = self.compile_Expression(var_def.initial_value)
        if isinstance(value.initializer, ir.Constant):
            value.initializer = value.initializer.inttoptr(var_def.decl.type_ref.type.as_native())
        return value

    # noinspection PyTypeChecker
    def compile_Expression(self, expr: Expression, ref: bool = False) -> ir.Value:
        if expr.kind is ASTKind.ConstExpr:
            return self.compile_ConstExpr(expr)
        elif expr.kind is ASTKind.CastExpr:
            return self.compile_CastExpr(expr)
        elif expr.kind is ASTKind.CallExpr:
            return self.compile_CallExpr(expr)
        elif expr.kind is ASTKind.IdentExpr:
            return self.compile_IdentExpr(expr, ref)
        elif expr.kind is ASTKind.GetExpr:
            return self.compile_GetExpr(expr, ref)
        elif expr.kind is ASTKind.OpExpr:
            return self.compile_OpExpr(expr)

        raise CompileError(f"Unknown expression {expr} with type {expr.kind}")

    def compile_GetExpr(self, get: GetExpression, ref: bool) -> ir.Value:
        accessed = self.compile_Expression(get.left, ref)
        name = get.right.actual()

        return self.ir_builder.gep() if ref else self.ir_builder.extract_value(accessed, )

    def compile_OpExpr(self, op: OpExpression) -> ir.Value:
        if len(op.operands) == 2:
            if op.operator is TokenType.EQ:
                # noinspection PyTypeChecker
                left, right = self.compile_Expression(op.operands[0], True), self.compile_Expression(op.operands[1])
                return self.ir_builder.store(right, left)

            left, right = list(self.compile_Expression(operand) for operand in op.operands)

            if op.operator in builtin_types.logic_binary_operators:
                if op.operator in self.logic_operators_map:
                    operator_map = self.logic_operators_map[op.operator]
                    if op.operands_type in builtin_types.signed_integers:
                        return self.ir_builder.icmp_signed(operator_map, left, right)
                    elif op.operands_type in builtin_types.unsigned_integers:
                        return self.ir_builder.icmp_unsigned(operator_map, left, right)
                    elif op.operands_type in builtin_types.floats:
                        return self.ir_builder.fcmp_ordered(operator_map, left, right)
                    else: CompileError(f"Unknown operands type {op.operands_type}")
                else: CompileError(f"Operator {op.operator} is not mapped")
            elif op.operator in builtin_types.arithmetic_binary_operators:
                raise NotImplementedError(builtin_types.arithmetic_binary_operators)
            else: raise CompileError(f"Unknown operator type {op.operator}")
        elif len(op.operands) == 1:
            if op.operator is TokenType.AMPERSAND:
                if op.operands[0].kind is not ASTKind.IdentExpr:
                    raise CompileError("Can get address only of ident expressions")
                # noinspection PyTypeChecker
                return self.compile_IdentExpr(op.operands[0], True)
            else: raise CompileError(f"Unknown operator type {op.operator}")
        else: raise CompileError(f"Unable to compile non binary/unary op {op} yet")

    def compile_IdentExpr(self, expr: IdentExpression, ref: bool) -> NamedValue:
        return self.require_var(expr.name.actual()) if ref else self.ir_builder.access_value(self.require_var(expr.name.actual()))

    def compile_CallExpr(self, expr: CallExpression) -> CallInstr:
        if expr.called.kind is ASTKind.IdentExpr:
            # noinspection PyTypeChecker
            ident: IdentExpression = expr.called
            func = self.require_func(ident.name.actual())

            params: list[Value] = []
            for param in expr.params:
                params.append(self.compile_Expression(param))

            return self.ir_builder.call(func, params)
        else: raise NotImplementedError("non static CallExpression not implemented yet")

    def compile_CastExpr(self, cast: CastExpression) -> ir.Value:
        # hope analyzer stripped wrong casts
        if cast.type.is_ptr:
            return self.ir_builder.inttoptr(self.compile_Expression(cast.expr), cast.type.as_native())
        raise CompileError(f"Cannot cast {cast.expr.type} to {cast.type}")

    def compile_ConstExpr(self, expr: ConstExpression) -> ir.Constant:
        if type(expr.value) is str:
            # noinspection PyTypeChecker
            value: str = expr.value

            bytes_value: bytes = value.encode("utf-8") + b"\0"
            array_element_type = expr.type.de_ptr().as_native()
            array_type = ir.ArrayType(array_element_type, len(bytes_value))
            array = ir.Constant(array_type, [ir.Constant(array_element_type, b) for b in bytes_value])

            var = ir.GlobalVariable(self.module, array_type, name=self.name_provider.get_name(value))
            var.initializer = array
            var.linkage = "private"
            var.global_constant = True
            var.alignment  = 1

            return var.bitcast(expr.type.as_native())
        else:
            value: object = expr.value
            return ir.Constant(expr.type.as_native(), value)