import logging
from datetime import timedelta

from flask import Flask

from VkBot import Bot, MessageParser
from flask_app.credentials import VK_API_TOKEN

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['DEBUG'] = True

vk_bot = Bot(
    access_token=VK_API_TOKEN,
    admins=(227725150, 138443566, 299443070),
    left_rooms=tuple(range(601, 620)),
    right_rooms=tuple(range(620, 639)),
    today_notification_timeout=timedelta(minutes=10)
)

message_parser = MessageParser()

from flask_app import routes  # noqa: F401,E402
