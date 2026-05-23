from typing import Self, Callable, override

from another_dependency_injector.wiring import inject, Wire

from .interfaces import IParser, WrongToken, MessageError
from ..ast import Statement, \
    Expression, ConstExpression, OpExpression, IdentExpression, CallExpression, GetExpression, FunctionDeclaration, \
    TypeReference, VarDeclaration, FunctionDefinition, CodeBlock, ReturnStatement, AST, File, FileMember, VarDefinition, \
    CastExpression
from ..iname import INameProvider, IName
from ..lex.interfaces import ILexer, TokenType, IToken
from ..stack import View, Stack

def any_type(*types: TokenType):
    return lambda a: a.type in types

class TokensView(View[IToken]):
    def __init__(self, stack: Stack[Self], data: list[IToken], start: int, end: int):
        super().__init__(stack, data, start, end)

    def after_to_first_type(self, *types: TokenType) -> Self:
        ind = self.find_next(*types, default=-1)
        return self.sub_view(self.pos, ind)

    def find_next[V](self, *types: TokenType, default: V = None) -> int | V:
        return super().find_next(any_type(*types), default=default)

    def find_next_pair(self, left: TokenType, right: TokenType) -> tuple[int, int] | tuple[None, None]:
        depth = 0
        enter_ind: int = 0
        for ind, token in self:
            if token.type is left:
                if depth == 0:
                    enter_ind = ind
                depth += 1
            elif token.type is right:
                if depth == 1:
                    return enter_ind, ind
                depth -= 1
        return None, None

    @override
    def split_all(self, *types: TokenType) -> list[Self]:
        return super().split_all(any_type(*types))


class Parser(IParser):
    lexer: ILexer
    tokens: list[IToken]
    name_provider: INameProvider
    views: Stack[TokensView]

    depth: int
    ignore_new_lines: bool

    constable: list[TokenType]

    unary_operators: list[TokenType]
    binary_operators: list[TokenType]

    binary_operators_sorted: list[list[TokenType]]

    @inject
    def __init__(self, lexer: ILexer = Wire[ILexer], name_provider: INameProvider = Wire[INameProvider]):
        self.lexer = lexer
        self.name_provider = name_provider

        self.ignore_new_lines = True
        self.tokens = []
        self.depth = 0
        self.constable = [TokenType.NUMBER, TokenType.STRING]

        self.unary_operators = [
            TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.AMPERSAND, TokenType.EXCLAIM
        ]

        self.binary_operators_sorted = [ # lower -> more priority
            [TokenType.PLUS, TokenType.MINUS],
            [TokenType.STAR, TokenType.SLASH],
            [TokenType.DOLLAR]
        ]

        self.binary_operators = list(token for tokens in self.binary_operators_sorted for token in tokens)

        self.read_all_tokens()
        self.views = Stack()
        self.views.push(TokensView(self.views, self.tokens, 0, len(self.tokens)))

    def skip_white_spaces(self):
        while self.probe().type in [TokenType.NEW_LINE, TokenType.INDENT]:
            self.consume()

    @property
    def pos(self):
        return self.view.pos

    def probe(self, offset: int = 0) -> IToken:
        return self.view[self.view.pos + offset]

    def consume(self):
        self.view.consume()

    def accept(self, *types: TokenType, offset: int = 0) -> IToken:
        token = self.probe(offset)
        if token.type in types:
            self.view.pos += 1
            return token
        raise WrongToken(token, *types)

    def __getitem__(self, ind: int) -> IToken:
        return self.tokens[ind]

    def read_all_tokens(self):
        while True:
            token = self.lexer.get_next_token()
            self.tokens.append(token)
            if token.type is TokenType.EOF:
                break

    def push_view(self, view: TokensView):
        self.views.append(view)

    def pop_view(self) -> TokensView:
        return self.views.pop()

    @property
    def view(self) -> TokensView:
        return self.views.top()

    def try_parse_indents(self) -> bool:
        d = 0
        while True:
            token = self.probe(d)
            if token.type is TokenType.INDENT:
                d += 1
                if d == self.depth:
                    self.view.pos += d
                    return True
            elif token.type is TokenType.NEW_LINE:
                self.view.pos += d + 1
                d = 0
            else:
                return False

    def parse_Name(self) -> IName:
        return self.name_provider.simple(self.accept(TokenType.IDENT).value_str)

    def parse_Statement(self) -> Statement:
        token = self.probe()
        if token.type is TokenType.RETURN:
            self.consume()
            expr = self.parse_Expression_to_end_of_line()
            return ReturnStatement(expr)
        return self.parse_Expression_to_end_of_line()

    def parse_Expression_to_end_of_line(self) -> Expression:
        with self.view.after_to_first_type(TokenType.NEW_LINE, TokenType.EOF).to_end:
            return self.parse_Expression()

    def parse_Expression(self) -> Expression:
        print("parse_Expression", self.view)
        if self.view[0].type is TokenType.LPAREN and self.view[-1].type is TokenType.RPAREN:
            with self.view.sub_view(1, self.view.len-1).to_end as v:
                return self.parse_Expression()

        mas: list[Expression | IToken] = []
        depth = 0
        prev_ind = 0
        for ind, token in self.view:
            if depth == 0 and token.type in self.binary_operators and (ind+1 >= self.view.len or self.view[ind+1].type != TokenType.RPAREN):
                if ind - prev_ind == 0:
                    continue
                with self.view.sub_view(prev_ind, ind).to_end:
                    mas.append(self.parse_Expression())
                mas.append(token)
                prev_ind = ind+1
            elif token.type is TokenType.LPAREN:
                depth += 1
            elif token.type is TokenType.RPAREN:
                depth -= 1

        if len(mas) == 0: # we got low level representation of previous expression
            if self.view.len == 1:
                if self.view[0].type in self.constable:
                    return self.parse_ConstExpression()
                elif self.view[0].type is TokenType.IDENT:
                    return self.parse_IdentExpression()
            elif self.view[0].type in self.unary_operators:
                with self.view.sub_view(1, self.view.len).to_end:
                    expr = self.parse_Expression()
                return OpExpression(self.view[0].type.name, [expr])
            else:
                first, second = self.view.find_next_pair(TokenType.LPAREN, TokenType.RPAREN)
                if first is not None:
                    if self.probe(second+1).type is TokenType.DOT:
                        called, params = self.view.split(first)

                        with called.to_end:
                            called_expr = self.parse_Expression()

                        params_expr: list[Expression] = []
                        if params.len > 0:
                            with params.sub_view(0, params.len-1).to_end:
                                for param_view in params.split_all(TokenType.COMMA):
                                    with param_view.to_end:
                                        params_expr.append(self.parse_Expression())
                        return CallExpression(called_expr, params_expr)
                    else:
                        with self.view.sub_view(first+1, second).to_end as v:
                            typ = self.parse_TypeReference()
                        with self.view.after(second+1).to_end:
                            expr = self.parse_Expression()
                        return CastExpression(typ, expr)

                ind = self.view.find_next(TokenType.DOT)
                if ind is not None:
                    left, right = self.view.split(ind)
                    with left.to_end:
                        left_expr = self.parse_Expression()
                    with right.to_end:
                        right_name = self.parse_Name()
                    return GetExpression(left_expr, right_name)

            raise MessageError(f"Unexpected start of expression {self.view[0]} in view {self.view}.")

        with self.view.sub_view(prev_ind, self.view.len).to_end:
            mas.append(self.parse_Expression())

        return self.parse_BinaryOpExpression_recursively(mas)

    def parse_BinaryOpExpression_recursively(self, mas: list[Expression | IToken]) -> OpExpression:
        for operators in self.binary_operators_sorted:
            for operator in operators:
                for i in range(len(mas)):
                    if isinstance(mas[i], IToken) and mas[i].type is operator:
                        left = mas[:i]
                        right = mas[i+1:]
                        left_expr = left[0] if len(left) == 1 else self.parse_BinaryOpExpression_recursively(left)
                        right_expr = right[0] if len(right) == 1 else self.parse_BinaryOpExpression_recursively(right)
                        return OpExpression(operator.name, [left_expr, right_expr])

    def parse_IdentExpression(self) -> IdentExpression:
        return IdentExpression(self.name_provider.simple(self.accept(TokenType.IDENT).value_str))

    def parse_ConstExpression(self) -> ConstExpression:
        return ConstExpression(self.accept(*self.constable).value)

    def parse_TypeReference(self) -> TypeReference:
        name = self.parse_Name()
        is_ptr = False
        if self.probe().type is TokenType.STAR:
            self.consume()
            is_ptr = True
        return TypeReference(name, is_ptr)

    def parse_VarDeclaration(self) -> VarDeclaration:
        name = self.parse_Name()
        self.accept(TokenType.COLON)
        type_ref = self.parse_TypeReference()

        return VarDeclaration(name, type_ref)

    def parse_VarDefinition_or_VarDeclaration(self) -> VarDefinition | VarDeclaration:
        decl = self.parse_VarDeclaration()
        if self.probe().type is TokenType.EQ:
            self.consume()
            with self.view.after_to_first_type(TokenType.EOF, TokenType.NEW_LINE).to_end as v:
                print("parse_VarDefinition_or_VarDeclaration", v)
                initial = self.parse_Expression()
            return VarDefinition(decl, initial)
        return decl

    def parse_FunctionDeclaration(self) -> FunctionDeclaration:
        print(self.view)
        params: list[VarDeclaration] = []

        self.accept(TokenType.FN)
        name = self.parse_Name()

        lparen = self.probe()
        if lparen.type is TokenType.LPAREN:
            raise WrongToken(self.probe(), TokenType.LPAREN)
        start_ind, end_ind = self.view.find_next_pair(TokenType.LPAREN, TokenType.RPAREN)
        if end_ind is None:
            raise MessageError(f"Expected closing parens pair at {lparen}")

        with self.view.sub_view(start_ind + 1, end_ind - 1).to_end as v:
            if self.view.len > 0:
                params_views = self.view.split_all(TokenType.COMMA)
                for view in params_views:
                    with view.to_end:
                        params.append(self.parse_VarDeclaration())
        self.accept(TokenType.RPAREN) # )

        self.accept(TokenType.ARROW_RIGHT)
        type_ref = self.parse_TypeReference()

        return FunctionDeclaration(name, type_ref, params)

    def parse_CodeBlock(self) -> CodeBlock:
        statements: list[Statement] = []

        while self.try_parse_indents():
            print(statements)
            statements.append(self.parse_Statement())

        return CodeBlock(statements)

    def parse_FunctionDefinition_or_FunctionDeclaration(self) -> FunctionDefinition | FunctionDeclaration:
        decl = self.parse_FunctionDeclaration()
        if self.probe().type is TokenType.COLON:
            self.consume()
            self.depth += 1
            block = self.parse_CodeBlock()
            self.depth -= 1
            return FunctionDefinition(decl, block)
        return decl

    def parse_File(self) -> File:
        asts: list[FileMember] = []
        self.skip_white_spaces()
        while self.probe().type is not TokenType.EOF:
            token = self.probe()
            if token.type is TokenType.FN:
                asts.append(self.parse_FunctionDefinition_or_FunctionDeclaration())
            elif token.type is TokenType.IDENT:
                asts.append(self.parse_VarDefinition_or_VarDeclaration())
            else:
                raise MessageError(f"Unexpected start of File member {token}")
            self.skip_white_spaces()
        return File(asts)