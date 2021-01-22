from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if False:  # Type hinting
    from sqlalchemy.orm.session import Session  # noqa

Base = declarative_base()


class LastRequests(Base):
    __tablename__ = 'LastRequests'
    peer_id = Column(Integer, primary_key=True, nullable=False)
    request_date = Column(DateTime, nullable=True)


class DutyRooms(Base):
    __tablename__ = 'DutyRooms'
    room = Column(Integer, primary_key=True)


class SyncTable(Base):
    __tablename__ = 'SyncTable'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    left_room = Column(Integer, nullable=False)
    right_room = Column(Integer, nullable=False)


class DBContext:
    def __init__(self, context_name):  # type: (str) -> None
        engine = create_engine(f'sqlite:///{context_name}.sqlite', echo=False)

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
