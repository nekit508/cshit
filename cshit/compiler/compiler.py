from typing import Self

from another_dependency_injector.wiring import inject, Wire
from llvmlite import ir, binding
from llvmlite.ir import Function, CallInstr, Value, NamedValue

from .interfaces import ICompiler, CompileError
from ..ast import FunctionDefinition, ASTKind, FunctionDeclaration, CodeBlock, Expression, \
    ConstExpression, File, FileMember, VarDeclaration, VarDefinition, CastExpression, CallExpression, Statement, \
    IdentExpression, ReturnStatement
from ..stack import StackableObject, Stack
from ..types import PtrType


class Context(StackableObject):
    functions: dict[str, Function]
    variables: dict[str, NamedValue]
    parent: Self | None

    def __init__(self, stack: Stack[Self], parent: Self | None = None):
        super().__init__(stack)
        self.functions = {}
        self.variables = {}
        self.parent = parent

    def register_variable(self, var: NamedValue) -> NamedValue | None:
        print(f"Registered variable {var.name}")
        if var.name in self.variables:
            return self.variables[var.name]
        self.variables[var.name] = var

    def resolve_variable(self, name: str, recursive: bool = False) -> NamedValue | None:
        if name not in self.variables:
            if self.parent is not None:
                func = self.parent.resolve_variable(name, True)
                if not recursive and func is None:
                    raise CompileError(f"Unknown variable {name}")
                return func
        return self.variables[name]

    def register_function(self, func: Function) -> Function | None:
        print(f"Registered function {func.name}")
        if func.name in self.functions:
            return self.functions[func.name]
        self.functions[func.name] = func
        self.register_variable(func)

    def resolve_function(self, name: str, recursive: bool = False) -> Function | None:
        if name not in self.functions:
            if self.parent is not None:
                func = self.parent.resolve_function(name, True)
                if not recursive and func is None:
                    raise CompileError(f"Unknown function {name}")
                return func
        return self.functions[name]

    @property
    def child(self):
        return Context(self.stack, self).to()


class Builder(StackableObject):
    builder: ir.IRBuilder

    def __init__(self, stack: Stack[Self], block: ir.Block | None = None, dummy: bool = False):
        super().__init__(stack)
        self.builder = None if dummy else ir.IRBuilder(block=block)

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

    @inject
    def __init__(self, ast: File, source: str = Wire["input_file"], output: str = Wire["output_file"]):
        self.ast = ast
        self.output = output

        self.init_llvm()

        self.module = ir.Module(name=source)

        self.context_stack = Stack()
        self.context_stack.append(Context(self.context_stack))

        self.builder_stack = Stack()
        self.builder_stack.append(Builder(self.builder_stack, dummy=True))

    @property
    def context(self) -> Context:
        return self.context_stack[-1]

    @property
    def builder(self) -> Builder:
        return self.builder_stack[-1]

    @property
    def ir_builder(self) -> ir.IRBuilder:
        return self.builder.builder

    def init_llvm(self):
        binding.initialize_native_target()
        binding.initialize_native_asmprinter()

    def compile(self):
        self.compile_File(self.ast)

        print("=================================   IR Code   =================================")
        print(self.module)
        mod = binding.parse_assembly(str(self.module))
        mod.verify()

        target = binding.Target.from_default_triple()
        target_machine = target.create_target_machine(codemodel="default")

        obj_code = target_machine.emit_object(mod)
        with open(self.output, "wb") as f:
            f.write(obj_code)

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

    def compile_FuncDecl(self, decl: FunctionDeclaration) -> ir.Function:
        out = ir.Function(self.module,
                          ir.FunctionType(decl.ret.type.as_native(),
                                          list(param.type_ref.type.as_native() for param in decl.params)
                                          ),
                          name = decl.name.actual())
        self.context.register_function(out)
        return out

    def compile_ReturnStmt(self, stmt: ReturnStatement):
        self.ir_builder.ret(self.compile_Expression(stmt.expr))

    def compile_FuncDef(self, func_def: FunctionDefinition) -> ir.Function:
        out = self.compile_FuncDecl(func_def.decl)
        with self.context.child, self.builder.child(out.append_basic_block("entry")):
            self.compile_CodeBlock(func_def.code)
        return out

    def compile_CodeBlock(self, block: CodeBlock):
        for stmt in block.statements:
            self.compile_Statement(stmt)

    def compile_Statement(self, stmt: Statement):
        print("compile_Statement", stmt)
        if stmt.kind is ASTKind.ReturnStmt:
            # noinspection PyTypeChecker
            return self.compile_ReturnStmt(stmt)
        elif stmt.kind is ASTKind.VarDef:
            # noinspection PyTypeChecker
            return self.compile_VarDef(stmt)
        elif stmt.kind is ASTKind.VarDecl:
            # noinspection PyTypeChecker
            return self.compile_VarDecl(stmt)
        # no statements parsed - maybe it is Expression
        elif isinstance(stmt, Expression):
            return self.compile_Expression(stmt)

        raise CompileError(f"Unknown statement {stmt} with kind {stmt.kind}")

    def compile_VarDecl(self, var_decl: VarDeclaration) -> ir.instructions.AllocaInstr:
        print("compile_GlobalVarDecl", var_decl.type_ref.type.as_native())
        out = self.ir_builder.alloca(var_decl.type_ref.type.as_native(), name=var_decl.name.actual())
        self.context.register_variable(out)
        return out

    def compile_VarDef(self, var_def: VarDefinition) -> ir.Value:
        value = self.compile_VarDecl(var_def.decl)
        self.ir_builder.store(self.compile_Expression(var_def.initial_value), value)
        return value

    def compile_GlobalVarDecl(self, var_decl: VarDeclaration) -> ir.GlobalVariable:
        print("compile_GlobalVarDecl", var_decl.type_ref.type.as_native())
        out = ir.GlobalVariable(self.module, var_decl.type_ref.type.as_native(), var_decl.name.actual())
        self.context.register_variable(out)
        return out

    def compile_GlobalVarDef(self, var_def: VarDefinition) -> ir.Value:
        value = self.compile_GlobalVarDecl(var_def.decl)
        value.initializer = self.compile_Expression(var_def.initial_value)
        if isinstance(value.initializer, ir.Constant):
            value.initializer = value.initializer.inttoptr(var_def.decl.type_ref.type.as_native())
        return value

    def compile_Expression(self, expr: Expression) -> ir.Value:
        if expr.kind is ASTKind.ConstExpr:
            # noinspection PyTypeChecker
            return self.compile_ConstExpr(expr)
        elif expr.kind is ASTKind.CastExpr:
            # noinspection PyTypeChecker
            return self.compile_CastExpr(expr)
        elif expr.kind is ASTKind.CallExpr:
            # noinspection PyTypeChecker
            return self.compile_CallExpr(expr)
        elif expr.kind is ASTKind.IdentExpr:
            # noinspection PyTypeChecker
            return self.compile_IdentExpr(expr)

        raise CompileError(f"Unknown expression {expr} with type {expr.kind}")

    def compile_IdentExpr(self, expr: IdentExpression) -> NamedValue:
        return self.ir_builder.load(self.context.resolve_variable(expr.name.actual()))

    def compile_CallExpr(self, expr: CallExpression) -> CallInstr:
        if expr.called.kind is ASTKind.IdentExpr:
            # noinspection PyTypeChecker
            ident: IdentExpression = expr.called
            func = self.context.resolve_function(ident.name.actual())

            params: list[Value] = []
            for param in expr.params:
                params.append(self.compile_Expression(param))

            print(params)
            print(expr.params)

            return self.ir_builder.call(func, params)
        else: NotImplementedError("non static CallExpression not implemented yet")

    def compile_CastExpr(self, expr: CastExpression) -> ir.Value:
        if isinstance(expr.type_ref.type, PtrType):
            val: ir.Value = self.compile_Expression(expr.expr)
            if isinstance(val, ir.Constant):
                val: ir.Constant = val
                return val.inttoptr(expr.type_ref.type.as_native())
            return self.builder.builder.inttoptr(val, expr.type_ref.type.as_native())
        else: raise NotImplementedError("Not ptr target casting not implemented yet")

    def compile_ConstExpr(self, expr: ConstExpression) -> ir.Constant:
        if type(expr.value) is str:
            # noinspection PyTypeChecker
            value: str = expr.value

            bytes_value: bytes = value.encode("utf-8") + b"\0"
            array_element_type = expr.type_ref.de_ptr().as_native()
            array_type = ir.ArrayType(array_element_type, len(bytes_value))
            array = ir.Constant(array_type, [ir.Constant(array_element_type, b) for b in bytes_value])

            var = ir.GlobalVariable(self.module, array_type, name="random_string_constant_name"+value)
            var.initializer = array
            var.linkage = "private"
            var.global_constant = True
            var.alignment  = 1

            return var.bitcast(expr.type_ref.as_native())
        else:
            value: object = expr.value
            return ir.Constant(expr.type_ref.as_native(), value)