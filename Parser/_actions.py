from enum import Enum, auto


class ActionsEnum(Enum):
    GET_DUTY_DATE = auto()
    SET_ROOM = auto()
    ADD_ROOMS = auto()
    REMOVE_ROOMS = auto()
    SHOW_LIST = auto()
    NOTIFY_TODAY = auto()
