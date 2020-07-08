from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from duty_bot.credentials import DB_FILE, VK_API_TOKEN6_6, VK_CALLBACK_SECRET6_6, WEBHOOK_SECRET, CONFIRMATION_TOKEN6_6
from duty_bot.logging_formatter import SensitiveFormatter
import vk_api
import logging

bot_logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)
for handler in logging.root.handlers:
    print(handler)
    handler.setFormatter(
        SensitiveFormatter(VK_CALLBACK_SECRET6_6, VK_API_TOKEN6_6, WEBHOOK_SECRET, CONFIRMATION_TOKEN6_6))


GROUP_ID = 192644739
OWNERS6_6 = (227725150, 138443566, 299443070, 180583820, 259344328)

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_FILE
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

vk_bot_session6_6 = vk_api.VkApi(token=VK_API_TOKEN6_6, api_version="5.103")

from duty_bot import routes
