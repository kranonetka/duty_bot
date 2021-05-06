__author__ = 'kranonetka'

from abc import ABC, abstractmethod

if False:  # Type hinting
    from VkBot import Bot  # noqa
    from typing import Any, Sequence


class Command(ABC):
    @abstractmethod
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        pass

    def __str__(self):
        return self.__class__.__name__

    __repr__ = __str__


class PrivilegedCommand(Command, ABC):
    pass


class GetDutyDateCommand(Command):
    def __init__(self, room):
        """
        :type room: int
        """
        self._room = room

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        vkbot_instance.notify_duty_date(peer_id, self._room)


class SetRoomsCommand(PrivilegedCommand):
    def __init__(self, rooms):
        """
        :type rooms: Sequence[int]
        """
        self._rooms = rooms

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        today = vkbot_instance.get_today_date()
        for room in self._rooms:
            vkbot_instance.set_room(peer_id, room, today)


class AddRoomsCommand(PrivilegedCommand):
    def __init__(self, rooms):
        """
        :type rooms: Sequence[int]
        """
        self._rooms = rooms

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        vkbot_instance.add_rooms(peer_id, self._rooms)


class RemoveRoomsCommand(PrivilegedCommand):
    def __init__(self, rooms):
        """
        :type rooms: Sequence[int]
        """
        self._rooms = rooms

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        vkbot_instance.remove_rooms(peer_id, self._rooms)


class ShowListCommand(Command):
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        vkbot_instance.show_list(peer_id)


class NotifyTodayCommand(Command):
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        vkbot_instance.show_today_rooms(peer_id)


class HelpCommand(Command):
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        vkbot_instance.help(peer_id)


class AddAdmins(PrivilegedCommand):
    def __init__(self, user_ids):
        """
        :type user_ids: Sequence[int]
        """
        self._user_ids = user_ids

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        for user_id in self._user_ids:
            vkbot_instance.add_admin(peer_id, user_id)


class RemoveAdmins(PrivilegedCommand):
    def __init__(self, user_ids):
        """
        :type user_ids: Sequence[int]
        """
        self._user_ids = user_ids

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> None
        for user_id in self._user_ids:
            vkbot_instance.remove_admin(peer_id, user_id)
