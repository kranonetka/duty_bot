from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if False:  # Type hinting
    from sqlalchemy.orm.session import Session  # noqa

Base = declarative_base()


class LastRequest(Base):
    __tablename__ = 'LastRequest'
    peer_id = Column(Integer, primary_key=True, nullable=False)
    request_date = Column(DateTime, nullable=True)


class DutyRoom(Base):
    __tablename__ = 'DutyRoom'
    room = Column(Integer, primary_key=True)


class SyncTable(Base):
    __tablename__ = 'SyncTable'
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    left_room = Column(Integer, nullable=False)
    right_room = Column(Integer, nullable=False)


class DBContext:
    def __init__(self):
        engine = create_engine('sqlite:///app_db.sqlite', echo=True)
        Base.metadata.create_all(engine)

        self._SessionMaker = sessionmaker(bind=engine)

    @contextmanager
    def session(self):  # type: () -> Session
        session = self._SessionMaker()  # type: Session
        try:
            yield session
            session.commit()
        except:  # noqa
            session.rollback()
            raise
        finally:
            session.close()


db_context = DBContext()
