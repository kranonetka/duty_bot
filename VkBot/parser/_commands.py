from abc import ABC, abstractmethod

if False:  # Type hinting
    from VkBot import Bot  # noqa
    from typing import Any


class Command(ABC):
    @abstractmethod
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        pass

    def __str__(self):
        return self.__class__.__name__

    __repr__ = __str__


class GetDutyDateCommand(Command):
    def __init__(self, room):
        """
        :type room: int
        """
        self._room = room

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        vkbot_instance.notify_duty_date(peer_id, self._room)


class SetRoomCommand(Command):
    def __init__(self, room):
        """
        :type room: int
        """
        self._room = room

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        today = vkbot_instance.get_today_date()
        vkbot_instance.set_room(peer_id, self._room, today)


class AddRoomsCommand(Command):
    def __init__(self, rooms):
        """
        :type rooms: Sequence[int]
        """
        self._rooms = rooms

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        vkbot_instance.add_rooms(peer_id, self._rooms)


class RemoveRoomsCommand(Command):
    def __init__(self, rooms):
        """
        :type rooms: Sequence[int]
        """
        self._rooms = rooms

    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        vkbot_instance.remove_rooms(peer_id, self._rooms)


class ShowListCommand(Command):
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        vkbot_instance.show_list(peer_id)


class NotifyTodayCommand(Command):
    def perform(self, vkbot_instance, peer_id):  # type: (Bot, int) -> Any
        vkbot_instance.show_today_rooms(peer_id)
