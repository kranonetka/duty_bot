from duty_bot import db


class LastRequests(db.Model):
    peer_id = db.Column(db.Integer, primary_key=True, nullable=False)
    request_date = db.Column(db.DateTime, nullable=True)


class DutyRooms(db.Model):
    room = db.Column(db.Integer, primary_key=True)


class SyncTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    left_room = db.Column(db.Integer, nullable=False)
    right_room = db.Column(db.Integer, nullable=False)
