from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# simple in-memory store
SETTINGS: dict[str, any] = {
    "theme_color": "#319795",
    "dark_mode": False,
    "items": []
}

class SettingsUpdate(BaseModel):
    theme_color: str | None = None
    dark_mode: bool | None = None
    items: list[dict] | None = None

@router.post('/update')
def update_settings(data: SettingsUpdate):
    if data.theme_color is not None:
        SETTINGS['theme_color'] = data.theme_color
    if data.dark_mode is not None:
        SETTINGS['dark_mode'] = data.dark_mode
    if data.items is not None:
        SETTINGS['items'] = data.items
    return SETTINGS
