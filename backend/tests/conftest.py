import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app

# Set testing environment
os.environ["TESTING"] = "true"

# Test database URL
TEST_DATABASE_URL = "postgresql://akvo:password@db:5432/agriconnect_test"

# Create test engine
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


@pytest.fixture(scope="session")
def test_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        # Clean up all tables after each test
        from models import Customer, Message, ServiceToken, User
        from models.knowledge_base import KnowledgeBase

        db.query(Message).delete()
        db.query(Customer).delete()
        db.query(KnowledgeBase).delete()  # Delete KBs before Users due to FK
        db.query(ServiceToken).delete()
        db.query(User).delete()
        db.commit()
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
