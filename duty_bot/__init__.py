from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from duty_bot.credentials import DB_FILE, VK_API_TOKEN6_6
import vk_api
import logging

logging.basicConfig(level=logging.DEBUG)

GROUP_ID = 192644739
OWNERS6_6 = (227725150, 246650048)

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_FILE
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

vk_bot_session6_6 = vk_api.VkApi(token=VK_API_TOKEN6_6, api_version="5.103")

from duty_bot import routes
