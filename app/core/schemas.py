from pydantic import BaseModel
from typing import Optional

class UserCache(BaseModel):
    id: int
    telegram_id: int | None = None
    username: Optional[str] = None
    promo_code: Optional[str] = None
    magazine_id: Optional[int] = None
    requests_left: int
    is_active: bool
    closed_menu_flag: bool
    first_catalog_request: bool
    first_info_request: bool
    show_intro_message: bool