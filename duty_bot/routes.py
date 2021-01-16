import json

import git
from flask import request, abort

from duty_bot import app, GROUP_ID
from duty_bot.credentials import CONFIRMATION_TOKEN6_6, VK_CALLBACK_SECRET6_6, WEBHOOK_SECRET
from duty_bot.functions import handle_event, is_valid_signature


@app.route("/", methods=["GET"])
def index():
    return "Hello, world!"


@app.route('/update_app', methods=['POST'])
def github_webhook():
    if "X-Hub-Signature" in request.headers:
        x_hub_signature = request.headers['X-Hub-Signature']
        if not is_valid_signature(x_hub_signature, request.data, WEBHOOK_SECRET):
            abort(401)
        event = request.headers.get('X-GitHub-Event')

        if event == "ping":
            response = json.dumps({'msg': 'Hi!'})
        elif event == "push":
            repo = git.Repo('.')
            origin = repo.remotes.origin
            pull_info = origin.pull()
    
            if len(pull_info) == 0 or pull_info[0].flags > 128:
                response = json.dumps({'msg': "Didn't pull any information from remote!"})
            else:
                commit_hash = pull_info[0].commit.hexsha
                response = f'Updated PythonAnywhere server to commit {commit_hash}'
        else:
            response = f'Unsupported event type: {event}'
        return response
    else:
        abort(404)


@app.route("/6_6", methods=["POST"])
def vk_callback():
    event = json.loads(request.data)
    print({key: val for key, val in event.items() if key != "secret"})
    if any(key not in event for key in ("type", "group_id", "secret")):
        abort(404)
    if event["type"] == "confirmation" and event["group_id"] == GROUP_ID:
        return CONFIRMATION_TOKEN6_6
    if event["secret"] != VK_CALLBACK_SECRET6_6:
        abort(401)
    handle_event(event)
    return "ok"
