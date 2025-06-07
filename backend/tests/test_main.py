from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {"message": "KyuyoBiyori API"}

def test_upload_and_list():
    files = {'file': ('test.txt', b'content')}
    res = client.post('/api/payslip/upload', files=files)
    assert res.status_code == 200
    data = res.json()
    assert 'id' in data

    list_res = client.get('/api/payslip')
    assert list_res.status_code == 200
    assert any(p['id'] == data['id'] for p in list_res.json())
