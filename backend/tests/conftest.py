import sys
import os
from types import ModuleType, SimpleNamespace

# ensure backend package can be imported as "backend"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
if 'backend' not in sys.modules:
    backend_pkg = ModuleType('backend')
    sys.modules['backend'] = backend_pkg
if 'backend.app' not in sys.modules:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'backend.app', os.path.join(ROOT_DIR, 'backend', 'app', '__init__.py')
    )
    backend_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend_app)
    sys.modules['backend.app'] = backend_app

# --- FastAPI stub ---
if 'fastapi' not in sys.modules:
    fastapi = ModuleType('fastapi')

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass
        def include_router(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def put(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def delete(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def put(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def delete(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code=400, detail=None):
            self.status_code = status_code
            self.detail = detail

    fastapi.FastAPI = FastAPI
    fastapi.APIRouter = APIRouter
    fastapi.UploadFile = object
    fastapi.File = lambda *a, **k: None
    fastapi.Form = lambda *a, **k: None
    fastapi.Depends = lambda *a, **k: None
    fastapi.HTTPException = HTTPException
    responses_mod = ModuleType('fastapi.responses')
    responses_mod.StreamingResponse = object
    fastapi.responses = responses_mod
    sys.modules['fastapi.responses'] = responses_mod

    testclient_mod = ModuleType('fastapi.testclient')
    class DummyResp:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json = json_data or {}
        def json(self):
            return self._json
    class TestClient:
        def __init__(self, app):
            self.app = app
        def get(self, *a, **k):
            return DummyResp()
        def post(self, *a, **k):
            return DummyResp()
        def put(self, *a, **k):
            return DummyResp()
        def delete(self, *a, **k):
            return DummyResp()
    testclient_mod.TestClient = TestClient
    fastapi.testclient = testclient_mod
    sys.modules['fastapi'] = fastapi
    sys.modules['fastapi.testclient'] = testclient_mod

# --- SQLAlchemy stub ---
if 'sqlalchemy' not in sys.modules:
    sqlalchemy = ModuleType('sqlalchemy')
    sqlalchemy.Integer = int
    sqlalchemy.String = str
    sqlalchemy.Date = str
    sqlalchemy.DateTime = str
    sqlalchemy.ForeignKey = lambda x: None
    class Column:
        def __init__(self, *a, **k):
            pass
    def create_engine(*a, **k):
        return None
    def sessionmaker(**k):
        def maker():
            return None
        return maker
    sqlalchemy.Column = Column
    sqlalchemy.create_engine = create_engine
    sqlalchemy.orm = ModuleType('sqlalchemy.orm')
    sqlalchemy.orm.sessionmaker = sessionmaker
    sqlalchemy.orm.relationship = lambda *a, **k: None
    sqlalchemy.orm.Session = object
    sqlalchemy.func = ModuleType('sqlalchemy.func')
    sqlalchemy.ext = ModuleType('sqlalchemy.ext')
    sqlalchemy.ext.declarative = ModuleType('sqlalchemy.ext.declarative')
    def _declarative_base():
        class Base:
            metadata = SimpleNamespace(create_all=lambda bind=None, **kw: None)
        return Base
    sqlalchemy.ext.declarative.declarative_base = _declarative_base
    sys.modules['sqlalchemy'] = sqlalchemy
    sys.modules['sqlalchemy.orm'] = sqlalchemy.orm
    sys.modules['sqlalchemy.ext'] = sqlalchemy.ext
    sys.modules['sqlalchemy.ext.declarative'] = sqlalchemy.ext.declarative

# --- Pydantic stub ---
if 'pydantic' not in sys.modules:
    pydantic = ModuleType('pydantic')
    class BaseModel:
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)
    pydantic.BaseModel = BaseModel
    sys.modules['pydantic'] = pydantic
