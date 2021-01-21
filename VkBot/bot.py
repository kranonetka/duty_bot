import datetime
import random
from itertools import zip_longest, filterfalse

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from .db import DBContext, DutyRooms, SyncTable

if False:  # Type hinting
    from sqlalchemy.orm import Session  # noqa
    from typing import Tuple, Sequence  # noqa


class Bot:
    ADMINS = {227725150, 138443566, 299443070}  # TODO: Должно быть задано в конструкторе
    LEFT_ROOMS = tuple(range(601, 620))  # TODO: Должно быть задано в конструкторе
    RIGHT_ROOMS = tuple(range(620, 639))  # TODO: Должно быть задано в конструкторе
    ALL_ROOMS = LEFT_ROOMS + RIGHT_ROOMS

    def __init__(
            self,
            access_token,
            admins=(),
            api_version='5.103'
    ):  # type: (str, Sequence[int], str) -> None
        self._admins = admins
        self._session = vk_api.VkApi(token=access_token, api_version=api_version)
        self._default_keyboard = self._get_keyboard()
        self._group_id = self._get_group_id()
        self._db_context = DBContext(str(self._group_id))
        self._fill_rooms_if_empty()
        self._check_sync()

    def show_list(self, peer_id):  # type: (int) -> None
        msg = self._build_rooms_list_msg()
        self._send_text(msg, peer_id)

    def help(self, peer_id):  # type: (int) -> None
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

    def set_room(self, peer_id, room, date):  # type: (int, int, datetime.date) -> None
        duty_rooms = self._get_all_duty_rooms()
        if room not in duty_rooms:
            msg = f'{room} комнаты нет среди дежурящих на 6-ом этаже'
            self._send_text(msg, peer_id)
        else:
            self._update_sync_table(room, date, duty_rooms)

    def add_rooms(self, peer_id, rooms):  # type: (int, Sequence[int]) -> None
        rooms_to_add = self._filter_adding_rooms(rooms)
        if rooms_to_add:
            self._add_rooms(rooms_to_add)
            msg = '✅ Добавлены комнаты: ' + ', '.join(map(str, rooms))
            self._send_text(msg, peer_id)

    def is_bot_group(self, id):  # type: (int) -> bool
        return id == self._group_id

    def _add_rooms(self, rooms):  # type: (Sequence[int]) -> None
        with self._db_context.session() as session:  # type: Session
            session.add_all(DutyRooms(room=room) for room in rooms)

    def _filter_adding_rooms(self, duty_rooms):  # type: (Sequence[int]) -> Tuple[int]
        rooms = tuple(filter(self.ALL_ROOMS.__contains__, duty_rooms))
        if rooms:
            duty_rooms = self._get_all_duty_rooms()
            return tuple(filterfalse(duty_rooms.__contains__, rooms))

    def _update_sync_table(self, room, date, current_rooms):  # type: (int, datetime.date, Sequence[int]) -> None
        left_rooms, right_rooms = self._split_rooms_by_side(current_rooms)
        if room in left_rooms:
            side = dict(left_room=room)
        else:
            side = dict(left_room=room)

        with self._db_context.session() as session:  # type: Session
            session.merge(SyncTable(id=0, date=date, **side))

    def _build_rooms_list_msg(self):  # type: () -> str
        left_rooms, right_rooms = self._get_side_splitted_rooms()

        msg = '📋 Дежурящие комнаты:\n'
        msg += '\n'.join(
            f'|{left:^5}|{right:^5}|'
            for left, right in zip_longest(left_rooms, right_rooms, fillvalue="___")
        )

        return msg

    def _get_duty_rooms_for_date(self, dest_date):  # type: (datetime.date) -> Tuple[int, int]
        with self._db_context.session() as session:  # type: Session
            sync_info: SyncTable = session.query(SyncTable).first()
            sync_date = sync_info.date  # type: datetime.date
            sync_left_room = sync_info.left_room  # type: int
            sync_right_room = sync_info.right_room  # type: int

        left_rooms, right_rooms = self._get_side_splitted_rooms()

        left_idx = left_rooms.index(sync_left_room)
        right_idx = right_rooms.index(sync_right_room)

        offset = (dest_date - sync_date).days

        left_idx = (left_idx + offset) % len(left_rooms)
        right_idx = (right_idx + offset) % len(right_rooms)
        return left_rooms[left_idx], right_rooms[right_idx]

    def _get_side_splitted_rooms(self):  # type: () -> Tuple[Tuple[int], Tuple[int]]
        all_rooms = self._get_all_duty_rooms()
        return self._split_rooms_by_side(all_rooms)

    def _get_all_duty_rooms(self):  # type: () -> Tuple[int]
        with self._db_context.session() as session:  # type: Session
            rooms = session.query(DutyRooms).order_by(DutyRooms.room).all()  # type: Sequence[DutyRooms]
            return tuple(room.room for room in rooms)

    def _split_rooms_by_side(self, rooms):  # type: (Sequence[int]) -> Tuple[Tuple[int], Tuple[int]]
        left_rooms = tuple(filter(self.LEFT_ROOMS.__contains__, rooms))
        right_rooms = tuple(filter(self.RIGHT_ROOMS.__contains__, rooms))

        return left_rooms, right_rooms

    def _get_keyboard(self):  # type: () -> str
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button(
            label='Кто дежурит сегодня',
            color=VkKeyboardColor.POSITIVE,
            payload={
                'command': 'main'
            }
        )
        return keyboard.get_keyboard()

    def _fill_rooms_if_empty(self):
        with self._db_context.session() as session:  # type: Session
            if not session.query(DutyRooms).count():
                session.add_all(DutyRooms(room=room) for room in self.ALL_ROOMS)

    def _check_sync(self):
        with self._db_context.session() as session:  # type: Session
            if session.query(SyncTable).first() is None:
                left_rooms, right_rooms = self._get_side_splitted_rooms()
                sync_info = SyncTable(
                    id=0,
                    date=datetime.date.today(),
                    left_room=left_rooms[0],
                    right_room=right_rooms[0]
                )
                session.add(sync_info)

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
