from fastapi.testclient import TestClient
from backend.app.main import app
from datetime import date, timedelta

client = TestClient(app)

def test_read_root():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {"message": "KyuyoBiyori API"}

def test_upload_and_list():
    files = {'file': ('test.txt', b'gross:120\nnet:100\ndeduction:20')}
    res = client.post('/api/payslip/upload', files=files)
    assert res.status_code == 200
    preview = res.json()
    assert preview['gross_amount'] == 120

    save_res = client.post('/api/payslip/save', json={
        'filename': preview['filename'],
        'date': '2024-01-01',
        'type': 'salary',
        'gross_amount': preview['gross_amount'],
        'net_amount': preview['net_amount'],
        'deduction_amount': preview['deduction_amount'],
    })
    assert save_res.status_code == 200
    saved = save_res.json()
    assert 'id' in saved

    list_res = client.get('/api/payslip')
    assert list_res.status_code == 200
    assert any(p['id'] == saved['id'] for p in list_res.json())


def test_summary_and_stats():
    today = date.today()
    this_month = today.replace(day=1)
    prev_month = (this_month - timedelta(days=1)).replace(day=1)

    files1 = {'file': ('this.txt', b'gross:120\nnet:100\ndeduction:20')}
    files2 = {'file': ('prev.txt', b'gross:100\nnet:80\ndeduction:20')}

    preview1 = client.post('/api/payslip/upload', files=files1).json()
    preview2 = client.post('/api/payslip/upload', files=files2).json()

    client.post('/api/payslip/save', json={
        'filename': preview1['filename'],
        'date': this_month.isoformat(),
        'type': 'salary',
        'gross_amount': preview1['gross_amount'],
        'net_amount': preview1['net_amount'],
        'deduction_amount': preview1['deduction_amount']
    })

    client.post('/api/payslip/save', json={
        'filename': preview2['filename'],
        'date': prev_month.isoformat(),
        'type': 'salary',
        'gross_amount': preview2['gross_amount'],
        'net_amount': preview2['net_amount'],
        'deduction_amount': preview2['deduction_amount']
    })

    summary = client.get('/api/payslip/summary').json()
    assert summary['net_this_month'] == 100
    assert summary['diff_vs_prev_month'] == 20

    stats = client.get('/api/payslip/stats?target=net').json()
    assert this_month.strftime('%Y-%m') in stats['labels']


def test_filter_and_delete():
    preview = client.post('/api/payslip/upload', files={'file': ('f.txt', b'gross:100\nnet:90')}).json()
    save = client.post('/api/payslip/save', json={
        'filename': preview['filename'],
        'date': '2023-06-01',
        'type': 'bonus',
        'gross_amount': preview['gross_amount'],
        'net_amount': preview['net_amount'],
        'deduction_amount': preview['deduction_amount']
    }).json()

    filtered = client.get('/api/payslip/list?year=2023&kind=bonus').json()
    assert any(p['id'] == save['id'] for p in filtered)

    del_res = client.delete(f'/api/payslip/delete?payslip_id={save["id"]}')
    assert del_res.status_code == 200
    remaining = client.get('/api/payslip/list?year=2023&kind=bonus').json()
    assert all(p['id'] != save['id'] for p in remaining)


def test_update_and_reparse():
    preview = client.post('/api/payslip/upload', files={'file': ('u.txt', b'gross:200\nnet:180\ndeduction:20')}).json()
    save = client.post('/api/payslip/save', json={
        'filename': preview['filename'],
        'date': '2024-02-01',
        'type': 'salary',
        'gross_amount': preview['gross_amount'],
        'net_amount': preview['net_amount'],
        'deduction_amount': preview['deduction_amount'],
        'items': preview['items'],
    }).json()

    detail = client.get(f'/api/payslip/{save["id"]}').json()
    assert detail['id'] == save['id']
    assert detail['items']

    updated = client.put('/api/payslip/update', json={
        'id': save['id'],
        'filename': save['filename'],
        'date': '2024-03-01',
        'type': 'salary',
        'gross_amount': 210,
        'net_amount': 190,
        'deduction_amount': 20,
        'items': detail['items'],
    }).json()
    assert updated['gross_amount'] == 210

    resp = client.post('/api/payslip/reparse', json={'items': detail['items']}).json()
    assert all('category' in it for it in resp)


def test_stats_filters_and_breakdown():
    # create two payslips with different types and items
    p1 = client.post('/api/payslip/upload', files={'file': ('a.txt', b'gross:100\nnet:90\ndeduction:10')}).json()
    p2 = client.post('/api/payslip/upload', files={'file': ('b.txt', b'gross:200\nnet:150\ndeduction:50')}).json()

    client.post('/api/payslip/save', json={
        'filename': p1['filename'],
        'date': '2024-04-01',
        'type': 'bonus',
        'gross_amount': p1['gross_amount'],
        'net_amount': p1['net_amount'],
        'deduction_amount': p1['deduction_amount'],
        'items': [{'name': 'tax', 'amount': -10, 'category': 'deduction'}]
    })

    client.post('/api/payslip/save', json={
        'filename': p2['filename'],
        'date': '2024-05-01',
        'type': 'salary',
        'gross_amount': p2['gross_amount'],
        'net_amount': p2['net_amount'],
        'deduction_amount': p2['deduction_amount'],
        'items': [{'name': 'tax', 'amount': -20, 'category': 'deduction'}]
    })

    stats = client.get('/api/payslip/stats?period=yearly&target=gross&kind=bonus').json()
    assert stats['data']

    breakdown = client.get('/api/payslip/breakdown?year=2024&category=deduction').json()
    assert 'tax' in breakdown['labels']


def test_export_and_settings_update():
    # create a payslip for export
    preview = client.post('/api/payslip/upload', files={'file': ('exp.txt', b'gross:50\nnet:40\ndeduction:10')}).json()
    client.post('/api/payslip/save', json={
        'filename': preview['filename'],
        'date': '2024-06-01',
        'type': 'salary',
        'gross_amount': preview['gross_amount'],
        'net_amount': preview['net_amount'],
        'deduction_amount': preview['deduction_amount']
    })

    res_json = client.get('/api/payslip/export?format=json')
    assert res_json.status_code == 200
    assert isinstance(res_json.json(), list)

    res_csv = client.get('/api/payslip/export?format=csv')
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv.headers['content-type']

    upd = client.post('/api/settings/update', json={'theme_color': '#ffffff'})
    assert upd.status_code == 200
    assert upd.json()['theme_color'] == '#ffffff'


def test_unknown_item_fallback():
    resp = client.post('/api/payslip/upload', files={'file': ('unk.txt', b'FooBar:30')})
    assert resp.status_code == 200
    preview = resp.json()
    assert preview['items']
    assert preview['items'][0]['category'] in ['payment', 'deduction']
