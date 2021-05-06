__author__ = 'kranonetka'

import json

import git
from flask import request, abort

from flask_app import app, vk_bot
from flask_app.credentials import WEBHOOK_SECRET, CONFIRMATION_TOKEN, VK_CALLBACK_SECRET
from flask_app.functions import is_valid_signature, handle_event


@app.route('/', methods=['GET'])
def index():
    return 'Hello, world!'


@app.route('/update_app', methods=['POST'])
def github_webhook():
    if 'X-Hub-Signature' in request.headers:
        x_hub_signature = request.headers['X-Hub-Signature']
        if not is_valid_signature(x_hub_signature, request.data, WEBHOOK_SECRET):
            abort(401)
        event = request.headers.get('X-GitHub-Event')

        if event == 'ping':
            response = json.dumps({'msg': 'Hi!'})
        elif event == 'push':
            repo = git.Repo('.')
            origin = repo.remotes.origin
            pull_info = origin.pull()

            if len(pull_info) == 0 or pull_info[0].flags > 128:
                response = json.dumps({'msg': 'Didn\'t pull any information from remote!'})
            else:
                commit_hash = pull_info[0].commit.hexsha
                response = f'Updated PythonAnywhere server to commit {commit_hash}'
        else:
            response = f'Unsupported event type: {event}'
        return response
    else:
        abort(404)


@app.route('/6_6', methods=['POST'])
def vk_callback():
    event = json.loads(request.data)  # type: dict

    secret = event.pop('secret', None)

    print(event)

    if any(key not in event for key in ('type', 'group_id')):
        abort(404)

    if event['type'] == 'confirmation':
        if vk_bot.is_bot_id(event['group_id']):
            return CONFIRMATION_TOKEN

    if secret != VK_CALLBACK_SECRET:
        abort(401)

    handle_event(event)

    return "ok"
