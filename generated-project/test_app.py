import pytest
import os
from app import app, init_db, DB_NAME

@pytest.fixture
def client():
    app.config['TESTING'] = True
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    init_db()
    with app.test_client() as client:
        yield client
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Study Planner' in response.data

def test_add_task(client):
    response = client.post('/add', data={
        'title': 'Read Chapter 1',
        'subject': 'Mathematics',
        'deadline': '2023-12-31'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Read Chapter 1' in response.data
    assert b'Mathematics' in response.data
