from fastapi.testclient import TestClient
from backend.app.main import app
from datetime import date, timedelta

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


def test_summary_and_stats():
    today = date.today()
    this_month = today.replace(day=1)
    prev_month = (this_month - timedelta(days=1)).replace(day=1)

    files1 = {'file': ('this.txt', b'content')}
    files2 = {'file': ('prev.txt', b'content')}

    client.post('/api/payslip/upload', files=files1, data={
        'date_str': this_month.isoformat(),
        'net_amount': '100',
        'gross_amount': '120',
        'deduction_amount': '20'
    })

    client.post('/api/payslip/upload', files=files2, data={
        'date_str': prev_month.isoformat(),
        'net_amount': '80',
        'gross_amount': '100',
        'deduction_amount': '20'
    })

    summary = client.get('/api/payslip/summary').json()
    assert summary['net_this_month'] == 100
    assert summary['diff_vs_prev_month'] == 20

    stats = client.get('/api/payslip/stats?target=net').json()
    assert this_month.strftime('%Y-%m') in stats['labels']
