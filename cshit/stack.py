from dataclasses import dataclass
from typing import Self, Any, Callable

from cshit.utils import pretty_list


class Stack[T:"StackableObject"](list[T]):
    def __init__(self):
        super().__init__()

    def push(self, obj: T):
        self.append(obj)

    @property
    def top(self) -> T:
        return None if len(self) == 0 else self[-1]


class StackableObject:
    stack: Stack[Self] | None

    def __init__(self, stack: Stack[Self] | None):
        self.set_stack(stack)

    def set_stack(self, stack: Stack[Self] | None):
        self.stack = stack

    def to(self, data: tuple[Any, ...] = ()) -> "StackableObjectRef[Self]":
        return StackableObjectRef(self, self.stack, data)

    def handle(self, obj: Self, data: tuple[Any, ...]):
        pass


class StackableObjectRef[T:StackableObject]:
    obj: T
    stack: Stack[T]
    data: tuple[Any, ...]

    def __init__(self, obj: T, stack: Stack[T], data: tuple[Any, ...] = ()):
        self.obj = obj
        self.stack = stack
        self.data = data

    def __enter__(self) -> T:
        self.stack.append(self.obj)
        return self.stack.top

    def __exit__(self, exc_type, exc_val, exc_tb):
        obj = self.stack.pop()
        assert self.obj is obj, "popped object must be equal to pushed object"
        obj.handle(self.stack.top, self.data)


@dataclass
class ViewIter[T]:
    mas: list[T]
    start: int
    pos: int
    end: int

    def __next__(self) -> tuple[int, T]:
        if self.pos < self.end:
            out = (self.pos - self.start, self.mas[self.pos])
            self.pos += 1
            return out
        else: raise StopIteration

    def __iter__(self) -> Self:
        return self


@dataclass
class ReversedViewIter[T]:
    mas: list[T]
    start: int
    pos: int
    end: int

    def __next__(self) -> tuple[int, T]:
        if self.pos >= self.start:
            out = (self.pos - self.start, self.mas[self.pos])
            self.pos -= 1
            return out
        else: raise StopIteration


@dataclass
class ReverseViewIterProvider[T]: # constructed like ViewIter
    mas: list[T]
    start: int
    pos: int
    end: int

    def __iter__(self) -> ReversedViewIter[T]: # from end to pos
        return ReversedViewIter(self.mas, self.pos, self.end-1, self.end)


class View[T](StackableObject):
    data: list[T]
    pos: int     # relative
    start: int   # absolute
    end: int     # absolute
    len: int

    def __init__(self, stack: Stack[Self], data: list[T], start: int, end: int):
        super().__init__(stack)
        self.data = data
        self.pos = 0
        self.end, self.start = end, start
        self.len = self.end - self.start

    @property
    def to_pos(self) -> StackableObjectRef[Self]:
        return self.to((False, ))

    @property
    def to_end(self) -> StackableObjectRef[Self]:
        return self.to((True, ))

    @property
    def ignore(self) -> StackableObjectRef[Self]:
        return self.to()

    def to_absolute(self, relative: int) -> int:
        return self.start + relative if relative >= 0 else self.end + relative + 1

    def to_relative(self, absolute: int) -> int:
        return absolute - self.start

    def __getitem__(self, ind: int) -> T:
        if ind >= self.len:
            raise IndexError(f"View index {ind} of of range for len {self.len}")
        return self.data[self.to_absolute(ind)]

    def remain(self) -> int:
        """ Current token is included """
        return self.len - self.pos

    def get(self) -> T:
        return self[self.pos]

    def consume(self) -> T:
        out = self.get()
        self.pos += 1
        return out

    def split(self, ind: int = 0) -> tuple[Self, Self]:
        """ exclusive """
        return self.before(ind-1), self.after(ind+1)

    def split_all(self, pred: Callable[[T], bool]) -> list[Self]:
        """ exclusive """
        out: list[Self] = []
        prev = 0
        for ind, obj in self:
            if pred(obj):
                # noinspection PyTypeChecker
                out.append(self.sub_view(prev, ind))
                prev = ind+1
        # noinspection PyTypeChecker
        out.append(self.after(prev))
        return out


    def sub_view(self, f: int, t: int) -> Self:
        """[)"""
        return type(self)(self.stack, self.data, self.to_absolute(f), self.to_absolute(t))

    def before(self, i: int | None = None) -> Self:
        """ inclusive """
        return self.sub_view(0, (self.pos if i is None else i) + 1)

    def after(self, i: int | None = None) -> Self:
        """ inclusive """
        return self.sub_view(self.pos if i is None else i, self.len)

    def find_next[V](self, pred: Callable[[T], bool], default: V = None) -> int | V:
        for ind, obj in self:
            if pred(obj):
                return ind
        return default

    def __repr__(self):
        return f"View {self.start}:{self.end} | {self.len} [{pretty_list(self.data[self.start:self.end])}] at {self.pos}"

    def handle(self, obj: Self, data: tuple[Any, ...]):
        if len(data) != 0:
            self.align(obj, self.len if data[0] else self.pos)

    def align(self, obj: Self, ind: int):
        obj.pos = obj.to_relative(self.to_absolute(ind))

    # TODO is it useful?
    def align_start(self, obj: Self):
        self.align(obj, self.start)

    def align_pos(self, obj: Self):
        self.align(obj, self.pos)

    def align_end(self, obj: Self):
        self.align(obj, self.end)

    def __iter__(self) -> ViewIter[T]:
        return ViewIter(self.data, self.start, self.to_absolute(self.pos), self.end)

    @property
    def reversed(self) -> ReverseViewIterProvider[T]:
        return ReverseViewIterProvider(self.data, self.start, self.to_absolute(self.pos), self.end)

    def __len__(self):
        return self.len
