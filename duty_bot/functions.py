from typing import Tuple, Callable, Union
from itertools import zip_longest
import re
import random
from datetime import datetime, timedelta
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import json
from duty_bot import vk_bot_session6_6, db, GROUP_ID, OWNERS6_6
from duty_bot.models import LastRequests, SyncTable, DutyRooms
import hmac
import hashlib

ALL_ROOMS = tuple(range(601, 639))
LEFT_ROOMS = tuple(range(601, 620))
RIGHT_ROOMS = tuple(range(620, 639))

default_keyboard = VkKeyboard(one_time=False)
default_keyboard.add_button(label="Кто дежурит сегодня", color=VkKeyboardColor.POSITIVE, payload={"command": "main"})
default_keyboard = default_keyboard.get_keyboard()

GMT7 = timedelta(hours=7)

WEEK_DAYS = {  # %a
    "Mon": "Понедельник",
    "Tue": "Вторник",
    "Wed": "Среда",
    "Thu": "Четверг",
    "Fri": "Пятница",
    "Sat": "Суббота",
    "Sun": "Воскресенье"
}

MONTHS = {
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


def send_text(message: str, peer_id: int, **kwargs) -> None:
    kwargs.update(random_id=random.getrandbits(64), keyboard=default_keyboard, message=message, peer_id=peer_id)
    print(kwargs)
    vk_bot_session6_6.method("messages.send", kwargs)


def greetings(peer_id: int) -> None:
    send_text("Привет!", peer_id)


def get_last_request(peer_id: int) -> Union[datetime, None]:
    last_request: LastRequests = LastRequests.query.filter_by(peer_id=peer_id).first()
    if last_request is not None:
        return last_request.request_date
    else:
        return None


def get_duty_rooms(date: datetime) -> Tuple[int, int]:
    sync_info = SyncTable.query.order_by(SyncTable.id.desc()).first()
    sync_date = sync_info.date
    sync_left_room = sync_info.left_room
    sync_right_room = sync_info.right_room
    offset = (date - sync_date).days
    all_rooms = [room.room for room in DutyRooms.query.all()]
    left_rooms = sorted(filter(LEFT_ROOMS.__contains__, all_rooms))
    right_rooms = sorted(filter(RIGHT_ROOMS.__contains__, all_rooms))
    left_room_index = left_rooms.index(sync_left_room)
    right_room_index = right_rooms.index(sync_right_room)
    left_room_index = (left_room_index + offset) % len(left_rooms)
    right_room_index = (right_room_index + offset) % len(right_rooms)
    return left_rooms[left_room_index], right_rooms[right_room_index]


def nothing(*args, **kwargs) -> None:
    pass


def set_last_request(peer_id: int, request_date: Union[datetime, None]) -> None:
    db.session.merge(LastRequests(peer_id=peer_id, request_date=request_date), load=True)
    db.session.commit()


def sync_rooms(date: datetime, from_peer_id: int, left_room: int = None, right_room: int = None) -> None:
    expected_left_room, expected_right_room = get_duty_rooms(date)
    date = datetime(date.year, date.month, date.day)
    db.session.add(SyncTable(
        date=date,
        left_room=left_room or expected_left_room,
        right_room=right_room or expected_right_room))
    db.session.commit()
    set_last_request(from_peer_id, None)


def today(peer_id: int, reply_to: int, today_date: datetime) -> None:
    left_room, right_room = get_duty_rooms(today_date)
    msg = "Сегодня дежурят {} и {}".format(left_room, right_room)
    send_text(msg, peer_id, reply_to=reply_to)
    set_last_request(peer_id, today_date)


def show_rooms(peer_id: int) -> None:
    all_rooms = [room.room for room in DutyRooms.query.all()]
    left_rooms = sorted(filter(LEFT_ROOMS.__contains__, all_rooms))
    right_rooms = sorted(filter(RIGHT_ROOMS.__contains__, all_rooms))
    msg = "Дежурящие комнаты:\n"
    msg += "\n".join(
        f"| {left:^3} | {right:^3} |"
        for left, right in zip_longest(left_rooms, right_rooms, fillvalue="___"))
    send_text(msg, peer_id)


def add_rooms(from_peer_id: int, date: datetime, *args) -> None:
    current_left_room, current_right_room = get_duty_rooms(date)
    for room in args:
        db.session.merge(DutyRooms(room=room))
    sync_rooms(date, from_peer_id, left_room=current_left_room, right_room=current_right_room)
    db.session.commit()


def remove_rooms(from_peer_id: int, date: datetime, *args) -> None:
    current_left_room, current_right_room = get_duty_rooms(date)
    db.session.query(DutyRooms).filter(DutyRooms.room.in_(args)).delete(synchronize_session="fetch")
    db.session.commit()

    all_rooms = [room.room for room in DutyRooms.query.all()]
    left_rooms = sorted(filter(LEFT_ROOMS.__contains__, all_rooms))
    right_rooms = sorted(filter(RIGHT_ROOMS.__contains__, all_rooms))

    if current_left_room in args:
        try:
            new_left_room = min(room for room in left_rooms if room > current_left_room)
        except ValueError:
            new_left_room = left_rooms[0]
        sync_rooms(date, from_peer_id, left_room=new_left_room)

    if current_right_room in args:
        try:
            new_right_room = min(room for room in right_rooms if room > current_right_room)
        except ValueError:
            new_right_room = right_rooms[0]
        sync_rooms(date, from_peer_id, right_room=new_right_room)


def parse_message(message_obj: dict) -> Tuple[Callable, Tuple]:
    if "action" in message_obj:
        if message_obj["action"].get("type") == "chat_invite_user":
            return greetings, (message_obj["peer_id"],)
    message_date = datetime.utcfromtimestamp(message_obj["date"]) + GMT7
    if "payload" in message_obj:
        payload = json.loads(message_obj["payload"])
        if payload.get("command") == "main":
            last_request = get_last_request(message_obj["peer_id"])
            if last_request is None or (message_date - last_request).total_seconds() >= 3600:
                return today, (
                    message_obj["peer_id"],
                    message_obj.get("conversation_message_id") or message_obj["id"],
                    message_date
                )
            else:
                return nothing, tuple()
    elif re.fullmatch(rf"(?:\[club{GROUP_ID}\|.+?\],?)?\s+когда\s+(\d+)\??", message_obj["text"].lower()):
        match = re.fullmatch(rf"(?:\[club{GROUP_ID}\|.+?\],?)?\s+когда\s+(\d+)\??", message_obj["text"].lower())
        target_room = int(match.group(1))
        all_rooms = [room.room for room in DutyRooms.query.all()]
        if target_room in all_rooms:
            current_left_room, current_right_room = get_duty_rooms(message_date)
            if 601 <= target_room <= 619:
                left_rooms = sorted(filter(LEFT_ROOMS.__contains__, all_rooms))
                offset = (left_rooms.index(target_room) - left_rooms.index(current_left_room)) % len(left_rooms)
            else:
                right_rooms = sorted(filter(RIGHT_ROOMS.__contains__, all_rooms))
                offset = (right_rooms.index(target_room) - right_rooms.index(current_right_room)) % len(right_rooms)
            dest_date = message_date + timedelta(days=offset)
            msg = "{} комната дежурит ориентировочно {} {} ({})".format(
                target_room,
                dest_date.day,
                MONTHS[dest_date.month],
                WEEK_DAYS[dest_date.strftime("%a")] if offset > 0 else "Сегодня"
                )
        else:
            msg = f"{target_room} комнаты нет среди дежурящих на 6-ом этаже"
        return send_text, (msg, message_obj["peer_id"])
    elif message_obj["from_id"] in OWNERS6_6:
        match = re.fullmatch(rf"(?:\[club{GROUP_ID}\|.+?\],?)?\s*(\d+)", message_obj['text'])
        if match:
            room = int(match.group(1))
            all_rooms = [room.room for room in DutyRooms.query.all()]
            if room in all_rooms:
                if 601 <= room <= 619:
                    return sync_rooms, (message_date, message_obj["peer_id"], room, None)
                else:
                    return sync_rooms, (message_date, message_obj["peer_id"], None, room)
            else:
                return send_text, (f"{room} комнаты нет среди дежурящих на 6-ом этаже", message_obj["peer_id"])
        match = re.fullmatch(rf"(?:\[club{GROUP_ID}\|.+?\],?)?\s*список", message_obj['text'].lower())
        if match:
            return show_rooms, (message_obj["peer_id"],)
        match = re.fullmatch(rf"(?:\[club{GROUP_ID}\|.+?\],?)?\s*\+\s*((?:\d+\s*)*(?:\d+))", message_obj['text'])
        if match:
            rooms = map(int, match.group(1).split())
            rooms = filter(ALL_ROOMS.__contains__, rooms)
            return add_rooms, (message_obj["peer_id"], message_date, *rooms,)
        match = re.fullmatch(rf"(?:\[club{GROUP_ID}\|.+?\],?)?\s*-\s*((?:\d+\s*)*(?:\d+))", message_obj['text'])
        if match:
            rooms = map(int, match.group(1).split())
            rooms = filter(ALL_ROOMS.__contains__, rooms)
            return remove_rooms, (message_obj["peer_id"], message_date, *rooms)
        return nothing, tuple()
    else:
        return nothing, tuple()


def is_valid_signature(x_hub_signature: str, data: bytes, private_key: str) -> bool:
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = getattr(hashlib, hash_algorithm)
    encoded_key = private_key.encode("ascii")
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


def handle_event(event) -> None:
    if event["type"] == "message_new":
        message_obj: dict = event["object"]["message"]
        action, args = parse_message(message_obj)
        action(*args)
