from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.execute("PRAGMA busy_timeout=30000")
