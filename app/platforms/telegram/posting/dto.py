from dataclasses import dataclass
from typing import Literal, Optional

# magazine - канал магазина
# author - твой авторский блог
# tech - технический канал (для кэширования media_id)
SourceType = Literal["magazine", "author", "tech"]

@dataclass(slots=True)
class PostingContext:
    source_type: SourceType
    channel_id: int
    magazine_id: Optional[int] = None # Только для magazine

