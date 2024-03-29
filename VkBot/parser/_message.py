__author__ = 'kranonetka'

from ._mention import Mention

if False:  # Type hinting
    from .commands import Command  # noqa


class Message:
    def __init__(self, command, mention=None):
        """
        :type command: Command
        :type mention: Optional[Mention]
        """
        self._command = command
        self._mention = mention

    @property
    def command(self):  # type: () -> Command
        return self._command

    @property
    def mention(self):  # type: () -> Mention
        return self._mention

    @mention.setter
    def mention(self, mention):  # type: (Mention) -> None
        if isinstance(mention, Mention):
            self._mention = mention
        else:
            raise TypeError(mention.__class__.__name__)

    def __repr__(self):
        return f'Message({self._mention}, {self._command})'
