import os
from datetime import datetime

from duty_bot import db, DB_FILE
from duty_bot.models import SyncTable, DutyRooms

if __name__ == "__main__":
    if not os.path.isfile("duty_bot/" + DB_FILE):
        db.create_all()
        db.session.bulk_save_objects((DutyRooms(room=i) for i in range(601, 639)))
        db.session.merge(SyncTable(
            id=0,
            date=datetime(year=2020, month=4, day=17),
            left_room=610,
            right_room=637)
        )
        db.session.commit()
