from .ast import *


class ASTVisitor:
    stack: list[AST]
    afters: dict[type[AST], Callable[[AST], list[AST]]]

    def __init__(self):
        self.stack = []
        self.afters = {
            FunctionDefinition: lambda ast: [ast.code],
            IfStatement: lambda ast: [] + ast.branches + [ast.else_block] if ast.else_block is not None else []
        }

    def get_afters[T:AST](self, ast: T) -> list[AST]:
        typ = type(ast)
        return self.afters[typ](ast) if typ in self.afters else []

    def collect_members_from_list_recursively(self, members_list: list) -> list[AST]:
        out: list[AST] = []

        for member in members_list:
            member_type = type(member)
            if issubclass(member_type, list):
                out += self.collect_members_from_list_recursively(member)
            elif issubclass(member_type, AST):
                out.append(member)

        return out

    def resolve_members_for_visit_before(self, ast: AST) -> list[AST]:
        afters = self.get_afters(ast)
        return list(member for member in self.collect_members_from_list_recursively(list(i for i in ast.__dict__.values())) if member not in afters)

    def resolve_members_for_visit_after(self, ast: AST) -> list[AST]:
        return self.get_afters(ast).copy()

    def enter[T:AST](self, ast: T):
        raise NotImplementedError()

    def visit[T:AST](self, ast: T):
        raise NotImplementedError()

    def exit[T:AST](self, ast: T):
        raise NotImplementedError()

    def visit_recursively(self, ast: AST):
        self.enter(ast)
        self.stack.append(ast)
        for member in self.resolve_members_for_visit_before(ast):
            self.visit_recursively(member)
        self.visit(ast)
        for member in self.resolve_members_for_visit_after(ast):
            self.visit_recursively(member)
        self.stack.pop()
        self.exit(ast)


    def get(self, offset: int = 0):
        return self.stack[-1 - offset]