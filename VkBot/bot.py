import random
from itertools import zip_longest

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from .db import db_context, DutyRoom

if False:  # Type hinting
    from sqlalchemy.orm import Session  # noqa


class Bot:
    LEFT_ROOMS = tuple(range(601, 620))
    RIGHT_ROOMS = tuple(range(620, 639))
    ALL_ROOMS = LEFT_ROOMS + RIGHT_ROOMS

    def __init__(self, access_token: str, peer_id: int, api_version='5.103'):
        self._session = vk_api.VkApi(token=access_token, api_version=api_version)
        self._peer_id = peer_id
        self._default_keyboard = self._get_keyboard()

    def show_list(self):
        all_rooms = self._get_all_duty_rooms()

        left_rooms = filter(Bot.LEFT_ROOMS.__contains__, all_rooms)
        right_rooms = filter(Bot.RIGHT_ROOMS.__contains__, all_rooms)

        msg = self._build_rooms_list_msg(left_rooms, right_rooms)

        self._send_text(msg)

    def _build_rooms_list_msg(self, left_rooms, right_rooms):
        msg = '📋 Дежурящие комнаты:\n'
        msg += '\n'.join(
            f'|{left:^5}|{right:^5}|'
            for left, right in zip_longest(left_rooms, right_rooms, fillvalue="___")
        )

        return msg

    def _get_all_duty_rooms(self):
        with db_context.session() as session:  # type: Session
            rooms = session.query(DutyRoom).order_by(DutyRoom.room).all()
            return [room.room for room in rooms]

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

    def _send_text(self, message: str, **kwargs) -> None:
        kwargs.update(
            random_id=random.getrandbits(64),
            keyboard=self._default_keyboard,
            message=message, peer_id=self._peer_id
        )
        self._session.method('messages.send', kwargs)
