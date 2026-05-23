from .ast import *


class ASTVisitor:
    stack: list[AST]

    def __init__(self):
        self.stack = []

    def collect_members_from_list_recursively(self, members_list: list) -> list[AST]:
        out: list[AST] = []

        for member in members_list:
            member_type = type(member)
            if issubclass(member_type, list):
                out += self.collect_members_from_list_recursively(member)
            elif issubclass(member_type, AST):
                out.append(member)

        return out

    def resolve_members_for_visit(self, ast: AST) -> list[AST]:
        return self.collect_members_from_list_recursively(list(i for i in ast.__dict__.values()))

    def visit[T:AST](self, ast: T):
        raise NotImplementedError()

    def visit_recursively(self, ast: AST):
        self.stack.append(ast)
        for member in self.resolve_members_for_visit(ast):
            self.visit_recursively(member)
        self.stack.pop()
        self.visit(ast)

    def get(self, offset: int = 0):
        return self.stack[-1 - offset]