__author__ = 'kranonetka'

import hashlib
import hmac

from parsimonious import ParseError

from VkBot import PrivilegedCommand
from flask_app import vk_bot, message_parser


def is_valid_signature(x_hub_signature, data, private_key):
    """
    :type x_hub_signature: str
    :type data: bytes
    :type private_key: str
    :rtype bool
    """
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = getattr(hashlib, hash_algorithm)
    encoded_key = private_key.encode("ascii")
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


def handle_event(event):  # type: (dict) -> None
    if event['type'] == 'message_new':
        message_obj = event['object']['message']

        try:
            message = message_parser.parse(message_obj['text'])
        except ParseError:
            return

        if message.mention:
            if not vk_bot.is_mentioned(message.mention):
                return

        if isinstance(message.command, PrivilegedCommand):
            if not vk_bot.is_admin(message_obj['from_id']):
                return

        message.command.perform(vk_bot, message_obj['peer_id'])
