from another_dependency_injector.wiring import inject, Wire

from .interfaces import ICompiler
from ..ast import AST, FunctionDefinition, ASTKind, FunctionDeclaration, CodeBlock, ReturnStatement, Expression, \
    ConstExpression, File, FileMember, VarDeclaration, VarDefinition, CastExpression
from llvmlite import ir, binding

class Compiler(ICompiler):
    ast: File
    module: ir.Module
    output: str

    @inject
    def __init__(self, ast: File, source: str = Wire["input_file"], output: str = Wire["output_file"]):
        self.ast = ast
        self.output = output

        self.init_llvm()

        self.module = ir.Module(name=source)

    def init_llvm(self):
        binding.initialize_native_target()
        binding.initialize_native_asmprinter()

    def compile(self):
        self.compile_File(self.ast)

        mod = binding.parse_assembly(str(self.module))
        print("=================================   Assembly Code   =================================")
        print(mod)
        mod.verify()

        target = binding.Target.from_default_triple()
        target_machine = target.create_target_machine(codemodel="default")

        obj_code = target_machine.emit_object(mod)
        with open(self.output, "wb") as f:
            f.write(obj_code)

    def compile_File(self, file: File):
        for member in file.members:
            print(f"member: {member.kind}")
            self.compile_FileMember(member)

    def compile_FileMember(self, file_member: FileMember):
        if file_member.kind is ASTKind.VarDecl:
            self.compile_GlobalVarDecl(file_member)
        elif file_member.kind is ASTKind.VarDef:
            self.compile_GlobalVarDef(file_member)
        elif file_member.kind is ASTKind.FuncDecl:
            self.compile_FuncDecl(file_member)

    def compile_FuncDecl(self, decl: FunctionDeclaration) -> ir.Function:
        return ir.Function(self.module,
                           ir.FunctionType(decl.ret.type.as_native(),
                                           list(param.type.type.as_native() for param in decl.params)
                                           ),
                           name = decl.name.actual())

    def compile_GlobalVarDecl(self, var_decl: VarDeclaration) -> ir.GlobalVariable:
        return ir.GlobalVariable(self.module, var_decl.type.type.as_native(), var_decl.name.actual())

    def compile_GlobalVarDef(self, var_def: VarDefinition) -> ir.Value:
        value = self.compile_GlobalVarDecl(var_def.decl)
        value.initializer = self.compile_Expression(var_def.initial_value)
        if isinstance(value.initializer, ir.Constant):
            value.initializer = value.initializer.inttoptr(var_def.decl.type.type.as_native())
        return value

    def compile_Expression(self, expr: Expression) -> ir.Value:
        if expr.kind is ASTKind.ConstExpr:
            return self.compile_ConstExpr(expr)
        elif expr.kind is ASTKind.CastExpr:
            return self.compile_CastExpr(expr)

    def compile_CastExpr(self, expr: CastExpression) -> ir.Constant:
        raise NotImplementedError()

    def compile_ConstExpr(self, expr: ConstExpression) -> ir.Constant:
        return ir.Constant(expr.type.as_native(), expr.value)

    def compile_func_def(self, definition: FunctionDefinition):
        func = self.compile_FunctionDeclaration(definition.decl)
        self.compile_code_block(definition.code, func, "entry")

    def compile_code_block(self, code_block: CodeBlock, func: ir.Function, label_name: str):
        builder = ir.IRBuilder(func.append_basic_block(label_name))

        for stmt in code_block.statements:
            if stmt.kind is ASTKind.ReturnStmt:
                self.compile_ReturnStatement(stmt, builder)

    def compile_ConstExpression(self, expr: ConstExpression, builder: ir.IRBuilder) -> ir.Constant:
        return ir.Constant(expr.type.as_native(), expr.value)

    def compile_FunctionDeclaration(self, decl: FunctionDeclaration) -> ir.Function:
        return ir.Function(self.module, ir.FunctionType(decl.ret_type.as_native(), list(type.as_native() for type in decl.param_types)), name = decl.name.actual())
