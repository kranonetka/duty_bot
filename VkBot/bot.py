import datetime
import random
from itertools import zip_longest, filterfalse

import pytz
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from .db import DBContext, DutyRooms, SyncTable, LastRequests

if False:  # Type hinting
    from sqlalchemy.orm import Session  # noqa
    from typing import Tuple, Sequence, Optional
    from .parser._mention import Mention

WEEK_DAYS_MAPPING = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

MONTHS_MAPPING = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря"
}


class Bot:
    def __init__(
            self,
            access_token,
            admins=(),
            left_rooms=tuple(range(601, 620)),
            right_rooms=tuple(range(620, 639)),
            today_notification_timeout=datetime.timedelta(minutes=15),
            tz=pytz.timezone('Asia/Tomsk'),
            api_version='5.103'
    ):
        """
        :type access_token: str
        :type admins: Tuple[int, ...]
        :param left_rooms: Tuple[int, ...]
        :param right_rooms: Tuple[int, ...]
        :param today_notification_timeout: datetime.timedelta
        :param tz: datetime.tzinfo
        :param api_version: str
        """
        self._admins = admins
        self._timeout = today_notification_timeout
        self._tz = tz

        self._available_left_rooms = left_rooms
        self._available_right_rooms = right_rooms
        self._available_rooms = left_rooms + right_rooms

        self._session = vk_api.VkApi(token=access_token, api_version=api_version)
        self._default_keyboard = self._get_keyboard()
        self._group_id = self._get_group_id()
        self._db_context = DBContext(str(self._group_id))

        self._fill_rooms_if_empty()
        self._resolve_sync()

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
            msg = self._build_room_missing_msg(room)
            self._send_text(msg, peer_id)
        else:
            self._update_sync_table(room, date, duty_rooms)
            self._reset_timeout(peer_id)

    def add_rooms(self, peer_id, rooms):  # type: (int, Sequence[int]) -> None
        rooms_to_add = self._filter_adding_rooms(rooms)
        if rooms_to_add:
            self._add_rooms(rooms_to_add)
            msg = '✅ Добавлены комнаты: ' + ', '.join(map(str, rooms))
            self._send_text(msg, peer_id)

    def remove_rooms(self, peer_id, rooms):  # type: (int, Sequence[int]) -> None
        rooms = self._filter_removing_rooms(rooms)
        if rooms:
            self._resolve_today_rooms(rooms)
            self._remove_rooms(rooms)
            msg = '❎ Убраны комнаты: ' + ', '.join(map(str, rooms))
            self._send_text(msg, peer_id)

    def notify_duty_date(self, peer_id, room):  # type: (int, int) -> None
        if self._is_room_present(room):
            date = self._get_duty_date(room)
            msg = self._build_duty_date_msg(room, date)
        else:
            msg = self._build_room_missing_msg(room)
        self._send_text(msg, peer_id)

    def show_today_rooms(self, peer_id):  # type: (int) -> None
        if self._is_timeout_exceeded(peer_id):
            today = self.get_today_date()
            left_room, right_room = self._get_duty_rooms_for_date(today)
            self._update_timeout(peer_id)
            msg = f'‼ Сегодня дежурят {left_room} и {right_room}'
            self._send_text(msg, peer_id)

    def is_mentioned(self, mention):  # type: (Mention) -> bool
        if mention.type == 'club':
            if mention.id == self._group_id:
                return True
        return False

    def is_bot_id(self, id):  # type:  (int) -> bool
        return id == self._group_id

    def is_admin(self, id):  # type: (int) -> bool
        return id in self._admins

    def get_today_date(self):  # type: () -> datetime.date
        return self.get_now_datetime().date()

    def get_now_datetime(self):  # type: () -> datetime.datetime
        return datetime.datetime.now(tz=self._tz)

    def _reset_timeout(self, peer_id):
        with self._db_context.session() as session:  # type: Session
            session.query(LastRequests). \
                filter(LastRequests.peer_id == peer_id). \
                delete(synchronize_session='fetch')

    def _update_timeout(self, peer_id):  # type: (int) -> None
        now = self.get_now_datetime()
        with self._db_context.session() as session:  # type: Session
            session.merge(LastRequests(peer_id=peer_id, request_date=now))

    def _is_timeout_exceeded(self, peer_id):  # type: (int) -> bool
        last_request = self._get_last_request_dt(peer_id)
        if last_request is None:
            return True

        now = self.get_now_datetime()
        now = now.replace(tzinfo=None)  # For subtracting
        if (now - last_request) > self._timeout:
            return True
        return False

    def _get_last_request_dt(self, peer_id):
        with self._db_context.session() as session:  # type: Session
            last_req = session.query(LastRequests). \
                filter(LastRequests.peer_id == peer_id). \
                first()  # type: Optional[LastRequests]
            if last_req is not None:
                return last_req.request_date

    def _get_duty_date(self, room):  # type: (int) -> datetime.date
        today = self.get_today_date()

        current_left_room, current_right_room = self._get_duty_rooms_for_date(today)
        left_rooms, right_rooms = self._get_side_splitted_rooms()
        if room in left_rooms:
            containing_side = left_rooms
            current_side_room = current_left_room
        else:
            containing_side = right_rooms
            current_side_room = current_right_room

        offset = (containing_side.index(room) - containing_side.index(current_side_room))
        offset %= len(containing_side)

        return today + datetime.timedelta(days=offset)

    def _build_duty_date_msg(self, room, date):  # type: (int, datetime.date) -> str
        today = self.get_today_date()
        if date == today:
            msg = f'{room} комната дежурит сегодня'
        else:
            msg = '{room} комната дежурит ориентировочно {day} {month} ({dayofweek})'.format(
                room=room,
                day=date.day,
                month=MONTHS_MAPPING[date.month],
                dayofweek=WEEK_DAYS_MAPPING[date.weekday()]
            )
        return msg

    def _build_room_missing_msg(self, room):  # type:  (int) -> str
        return f'{room} комнаты нет среди дежурящих на 6-ом этаже'

    def _is_room_present(self, room):  # type: (int) -> bool
        duty_rooms = self._get_all_duty_rooms()
        return room in duty_rooms

    def _resolve_today_rooms(self, rooms):  # type: (Sequence[int]) -> None
        today_date = self.get_today_date()
        left_room, right_room = self._get_duty_rooms_for_date(today_date)
        if left_room in rooms or right_room in rooms:
            left_rooms, right_rooms = self._get_side_splitted_rooms()

            if left_room in rooms:
                left_rooms = tuple(filterfalse(rooms.__contains__, left_rooms))
                new_left_room = min(
                    (room for room in left_rooms if room >= left_room),
                    default=left_rooms[0]
                )
            else:
                new_left_room = left_room

            if right_room in rooms:
                right_rooms = tuple(filterfalse(rooms.__contains__, right_rooms))
                new_right_room = min(
                    (room for room in right_rooms if room >= right_room),
                    default=right_rooms[0]
                )
            else:
                new_right_room = right_room

            with self._db_context.session() as session:  # type: Session
                session.merge(
                    SyncTable(
                        id=0,
                        date=today_date,
                        left_room=new_left_room,
                        right_room=new_right_room
                    )
                )

    def _remove_rooms(self, rooms):  # type: (Sequence[int]) -> None
        with self._db_context.session() as session:  # type: Session
            session.query(DutyRooms). \
                filter(DutyRooms.room.in_(rooms)). \
                delete(synchronize_session='fetch')

    def _add_rooms(self, rooms):  # type: (Sequence[int]) -> None
        with self._db_context.session() as session:  # type: Session
            session.add_all(DutyRooms(room=room) for room in rooms)

    def _filter_adding_rooms(self, rooms):  # type: (Sequence[int]) -> Tuple[int]
        allowed_rooms = tuple(filter(self._available_rooms.__contains__, rooms))
        if allowed_rooms:
            duty_rooms = self._get_all_duty_rooms()
            return tuple(filterfalse(duty_rooms.__contains__, allowed_rooms))

    def _filter_removing_rooms(self, rooms):  # type: (Sequence[int]) -> Tuple[int]
        allowed_rooms = tuple(filter(self._available_rooms.__contains__, rooms))
        if allowed_rooms:
            duty_rooms = self._get_all_duty_rooms()
            return tuple(filter(duty_rooms.__contains__, allowed_rooms))

    def _update_sync_table(self, room, date, current_rooms):  # type: (int, datetime.date, Sequence[int]) -> None
        left_rooms, right_rooms = self._split_rooms_by_side(current_rooms)
        if room in left_rooms:
            side = dict(left_room=room)
        else:
            side = dict(right_room=room)

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
        left_rooms = tuple(filter(self._available_left_rooms.__contains__, rooms))
        right_rooms = tuple(filter(self._available_right_rooms.__contains__, rooms))

        return left_rooms, right_rooms

    def _get_keyboard(self):  # type: () -> str
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button(
            label='Кто дежурит сегодня',
            color=VkKeyboardColor.POSITIVE
        )
        return keyboard.get_keyboard()

    def _fill_rooms_if_empty(self):
        with self._db_context.session() as session:  # type: Session
            if not session.query(DutyRooms).count():
                session.add_all(DutyRooms(room=room) for room in self._available_rooms)

    def _resolve_sync(self):
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
        kwargs = dict(
            random_id=random.getrandbits(64),
            keyboard=self._default_keyboard,
            message=message,
            peer_id=peer_id,
            **kwargs
        )
        self._session.method('messages.send', kwargs)
