__author__ = 'kranonetka'

import datetime
import random
from itertools import zip_longest, filterfalse

import git
import pytz
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from VkBot import __author_id__ as AUTHOR_ID
from .db import DBContext, DutyRooms, SyncTable, LastRequests, Admins

if False:  # Type hinting
    from sqlalchemy.orm import Session  # noqa
    from typing import Tuple, Sequence, Optional, List
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
        self._timeout = today_notification_timeout
        self._tz = tz

        self._available_left_rooms = left_rooms
        self._available_right_rooms = right_rooms
        self._available_rooms = left_rooms + right_rooms

        self._session = vk_api.vk_api.VkApiGroup(token=access_token, api_version=api_version)
        self._default_keyboard = self._get_keyboard()
        self._group_id = self._get_group_id()
        self._db_context = DBContext(str(self._group_id))

        self._fill_rooms_if_empty()
        self._add_admin_if_empty()
        self._resolve_sync()

    def show_list(self, peer_id):  # type: (int) -> None
        msg = self._build_rooms_list_msg()
        self._send_text(msg, peer_id)

    def help(self, peer_id):  # type: (int) -> None
        msg = self._build_help_msg()

        self._send_text(msg, peer_id)

    def set_room(self, peer_id, room, date):  # type: (int, int, datetime.date) -> None
        duty_rooms = self._get_all_duty_rooms()
        if room not in duty_rooms:
            msg = self._build_room_missing_msg(room)
            self._send_text(msg, peer_id)
        else:
            self._update_sync_table(room, date, duty_rooms)
            self._reset_timeout(peer_id)
            msg = self._build_room_setted_msg(room)
            self._send_text(msg, peer_id)

    def add_rooms(self, peer_id, rooms):  # type: (int, Sequence[int]) -> None
        rooms_to_add = self._filter_adding_rooms(rooms)
        if rooms_to_add:
            today = self.get_today_date()
            current_left, current_right = self._get_duty_rooms_for_date(today)

            self._add_rooms(rooms_to_add)

            self._set_rooms_for_date(current_left, current_right, today)

            msg = self._build_added_msg(rooms_to_add)
            self._send_text(msg, peer_id)

    def add_admin(self, peer_id, admin_id):  # type: (int, int) -> None
        if self.is_admin(admin_id):
            msg = self._build_already_admin_msg(admin_id)
            self._send_text(msg, peer_id)
        else:
            with self._db_context.session() as session:  # type: Session
                session.add(Admins(admin_id=admin_id))

            msg = self._build_admin_added_msg(admin_id)
            self._send_text(msg, peer_id)

    def remove_admin(self, peer_id, admin_id):  # type: (int, int) -> None
        if self.is_admin(admin_id):
            with self._db_context.session() as session:  # type: Session
                session.query(Admins). \
                    filter(Admins.admin_id == admin_id). \
                    delete(synchronize_session='fetch')
            msg = self._build_admin_removed_msg(admin_id)
            self._send_text(msg, peer_id)
        else:
            msg = self._build_not_a_admin_msg(admin_id)
            self._send_text(msg, peer_id)

    def remove_rooms(self, peer_id, rooms_to_remove):  # type: (int, Sequence[int]) -> None
        rooms_to_remove = self._filter_removing_rooms(rooms_to_remove)
        if rooms_to_remove:
            self._update_sync_before_removing(rooms_to_remove)
            self._remove_rooms(rooms_to_remove)
            msg = self._build_removed_msg(rooms_to_remove)
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
        with self._db_context.session() as session:  # type: Session
            return session.query(Admins).filter(Admins.admin_id == id).first() is not None

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

    def _build_admin_added_msg(self, admin_id):  # type: (int) -> str
        user = self._get_user_info(admin_id)
        msg = f'➕ Добавлен администратор: [id{user["id"]}|{user["first_name"]} {user["last_name"]}]'
        return msg

    def _build_already_admin_msg(self, admin_id):  # type: (int) -> str
        user = self._get_user_info(admin_id)
        msg = f'[id{user["id"]}|{user["first_name"]} {user["last_name"]}] уже является администратором'
        return msg

    def _build_admin_removed_msg(self, admin_id):  # type: (int) -> str
        user = self._get_user_info(admin_id)
        msg = f'➖ Убран администратор: [id{user["id"]}|{user["first_name"]} {user["last_name"]}]'
        return msg

    def _build_not_a_admin_msg(self, admin_id):  # type: (int) -> str
        user = self._get_user_info(admin_id)
        msg = f'[id{user["id"]}|{user["first_name"]} {user["last_name"]}] не является администратором'
        return msg

    def _build_room_missing_msg(self, room):  # type: (int) -> str
        return f'{room} комнаты нет среди дежурящих на 6-ом этаже'

    def _build_added_msg(self, rooms):  # type: (Sequence[int, ...]) -> str
        return '➕ Добавлены комнаты: ' + ', '.join(map(str, rooms))

    def _build_removed_msg(self, rooms):  # type: (Sequence[int, ...]) -> str
        return '➖ Убраны комнаты: ' + ', '.join(map(str, rooms))

    def _build_help_msg(self):  # type: () -> str
        msg = '❓ Команды:\n' \
              '🔸 Когда <комната> -- получить примерную дату, когда дежурит определённая комната\n' \
              '🔸 <комнаты> -- установить, что комнаты дежурят сегодня\n' \
              'Если комнат несколько, то разделяются пробелом\n' \
              '🔸 +<комнаты> -- добавить комнаты в список дежурящих\n' \
              '🔸 -<комнаты> -- убрать комнаты из списка дежурящих\n' \
              'Комнаты могут быть заданы как по одиночке, так и диапазоном. Например:\n' \
              '+601 603-606  -  добавит комнаты: 601, 603, 604, 605, 606\n' \
              '+<упоминание человека> - добавить администратора\n' \
              '-<упоминание человека> - убрать администратора' \
              '🔸 Помощь -- вывод этого сообщения\n' \
              '🔸 Кнопка "Кто дежурит сегодня" -- вывод дежурящих сегодня комнат\n' \
              '\n' \
              '🌟 Администраторы (могут менять комнаты):\n'

        admins = self._get_admins_info()

        msg += '\n'.join(
            f'[id{admin["id"]}|{admin["first_name"]} {admin["last_name"]}]'
            for admin in admins
        )

        repo = git.Repo('.')
        last_commit = repo.head.commit
        msg += '\n' \
               '\n' \
               f'revision: {last_commit.hexsha}\n' \
               f'{last_commit.message.strip()}'
        return msg

    def _is_room_present(self, room):  # type: (int) -> bool
        duty_rooms = self._get_all_duty_rooms()
        return room in duty_rooms

    def _update_sync_before_removing(self, rooms_to_remove):  # type: (Sequence[int]) -> None
        current_rooms = set(self._get_all_duty_rooms())
        after_deleting_rooms = sorted(current_rooms - set(rooms_to_remove))

        left_rooms, right_rooms = self._split_rooms_by_side(after_deleting_rooms)

        today = self.get_today_date()
        current_left, current_right = self._get_duty_rooms_for_date(today)

        new_left = min(
            (room for room in left_rooms if room >= current_left),
            default=left_rooms[0]
        )
        new_right = min(
            (room for room in right_rooms if room >= current_right),
            default=right_rooms[0]
        )

        with self._db_context.session() as session:  # type: Session
            session.merge(
                SyncTable(
                    id=0,
                    date=today,
                    left_room=new_left,
                    right_room=new_right
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

    def _set_rooms_for_date(self, left_room, right_room, date):  # type: (int, int, datetime.date) -> None
        with self._db_context.session() as session:  # type: Session
            session.merge(
                SyncTable(
                    id=0,
                    date=date,
                    left_room=left_room,
                    right_room=right_room
                )
            )

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

    def _get_admins_info(self):  # type: () -> List[dict]
        with self._db_context.session() as session:  # type: Session
            admin_ids = session.query(Admins).all()
            admin_ids = tuple(admin.admin_id for admin in admin_ids)
        admin_ids = ','.join(map(str, admin_ids))
        return self._session.method('users.get', {'user_ids': admin_ids})

    def _get_user_info(self, user_id):  # type: (int) -> dict
        return self._session.method('users.get', {'user_ids': user_id})[0]

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

    def _add_admin_if_empty(self):
        with self._db_context.session() as session:  # type: Session
            if not session.query(Admins).count():
                session.add(Admins(admin_id=AUTHOR_ID))

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

    def _build_room_setted_msg(self, room):
        return f'✔ {room} комната установлена дежурящей сегодня'
