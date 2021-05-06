__author__ = 'kranonetka'


class Mention:
    def __init__(self, type, id):  # type: (str, int) -> None
        self.type = type
        self.id = id

    def __str__(self):
        return f'{self.__class__.__name__}({self.type}{self.id})'

    __repr__ = __str__
