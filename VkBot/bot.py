import datetime
import random
from itertools import zip_longest

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from .db import DBContext, DutyRooms, SyncTable

if False:  # Type hinting
    from sqlalchemy.orm import Session  # noqa
    from typing import Tuple, Sequence  # noqa


class Bot:
    ADMINS = {227725150, 138443566, 299443070}
    LEFT_ROOMS = tuple(range(601, 620))
    RIGHT_ROOMS = tuple(range(620, 639))
    ALL_ROOMS = LEFT_ROOMS + RIGHT_ROOMS

    def __init__(
            self,
            access_token: str,
            admins=(),
            api_version='5.103'
    ):
        self._admins = admins
        self._session = vk_api.VkApi(token=access_token, api_version=api_version)
        self._default_keyboard = self._get_keyboard()
        self._group_id = self._get_group_id()
        self._db_context = DBContext(str(self._group_id))

    def show_list(self, peer_id):
        left_rooms, right_rooms = self._get_side_splitted_rooms()

        msg = self._build_rooms_list_msg(left_rooms, right_rooms)

        self._send_text(msg, peer_id)

    def help(self, peer_id):
        msg = '❓ Команды:\n' \
              '🔸 Когда <комната> -- получить примерную дату, когда дежурит определённая комната\n' \
              '🔸 <комната> -- установить, что комната дежурит сегодня\n' \
              '🔸 +<комнаты> -- добавить комнаты в список дежурящих\n' \
              '🔸 -<комнаты> -- убрать комнаты из списка дежурящих\n' \
              'Комнаты могут быть заданы как по одиночке, так и диапазоном. Например:\n' \
              '+601 603-606  -  добавит комнаты: 601, 603, 604, 605, 606\n' \
              '🔸 Помощь -- вывод этого сообщения\n' \
              '🔸 Кнопка "Кто дежурит сегодня" -- вывод дежурящих сегодня комнат'

        self._send_text(msg, peer_id)

    def set_room(self, room: int, date: datetime.date):
        pass

    def _build_rooms_list_msg(self, left_rooms, right_rooms):  # type: (Sequence[int], Sequence[int]) -> str
        msg = '📋 Дежурящие комнаты:\n'
        msg += '\n'.join(
            f'|{left:^5}|{right:^5}|'
            for left, right in zip_longest(left_rooms, right_rooms, fillvalue="___")
        )

        return msg

    def _get_duty_rooms_for_date(self, dest_date):  # type: (datetime.date) -> Tuple[int, int]
        with self._db_context.session() as session:  # type: Session
            sync_info: SyncTable = session.query(SyncTable).filter_by(id=0).first()
            sync_date = sync_info.date  # type: datetime.date
            sync_left_room = sync_info.left_room  # type: int
            sync_right_room = sync_info.right_room  # type: int

        left_rooms, right_rooms = self._get_side_splitted_rooms()

        synced_left_room_idx = left_rooms.index(sync_left_room)
        synced_right_room_idx = right_rooms.index(sync_right_room)

        offset = (dest_date - sync_date).days

        synced_left_room_idx = (synced_left_room_idx + offset) % len(left_rooms)
        synced_right_room_idx = (synced_right_room_idx + offset) % len(right_rooms)
        return left_rooms[synced_left_room_idx], right_rooms[synced_right_room_idx]

    def is_bot_group(self, id):  # type: (int) -> bool
        return id == self._group_id

    def _get_side_splitted_rooms(self):
        all_rooms = self._get_all_duty_rooms()
        return self._split_rooms_by_side(all_rooms)

    def _get_all_duty_rooms(self):  # type: () -> Tuple[int]
        with self._db_context.session() as session:  # type: Session
            rooms = session.query(DutyRooms).order_by(DutyRooms.room).all()  # type: Sequence[DutyRooms]
            return tuple(room.room for room in rooms)

    def _split_rooms_by_side(self, rooms):  # type: (Tuple[int]) -> Tuple[Tuple[int], Tuple[int]]
        left_rooms = tuple(filter(self.LEFT_ROOMS.__contains__, rooms))
        right_rooms = tuple(filter(self.RIGHT_ROOMS.__contains__, rooms))

        return left_rooms, right_rooms

    def _get_keyboard(self):
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button(
            label='Кто дежурит сегодня',
            color=VkKeyboardColor.POSITIVE,
            payload={
                'command': 'main'
            }
        )
        return keyboard.get_keyboard()

    def _get_group_id(self):  # type: () -> int
        response = self._session.method('groups.getById')
        return response[0]['id']

    def _send_text(self, message, peer_id, **kwargs):  # type: (str, int, dict) -> None
        kwargs.update(
            random_id=random.getrandbits(64),
            keyboard=self._default_keyboard,
            message=message,
            peer_id=peer_id
        )
        self._session.method('messages.send', kwargs)
