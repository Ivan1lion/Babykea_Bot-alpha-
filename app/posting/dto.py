from dataclasses import dataclass
from typing import Literal, Optional

UserGroup = Literal["group_1", "group_2", "all"]
SourceType = Literal["magazine", "my_channel"]


@dataclass(slots=True)
class PostingContext:
    source_type: SourceType
    channel_id: int

    magazine_id: Optional[int]
    user_group: UserGroup

    is_active: bool
