from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """ Base class for all SQLAlchemy ORM models. tracks table metadata across the entire application"""
    pass


