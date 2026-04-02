from typing import List, Optional
from pydantic import BaseModel


class ChapterOut(BaseModel):
    chapter_id: str
    title: str
    order: int


class KnowledgePointOut(BaseModel):
    kp_id: str
    name: str
    chapter_id: str
    section: Optional[str] = None
    aliases: Optional[str] = None
    source: Optional[str] = None


class ChapterDetailOut(BaseModel):
    chapter: ChapterOut
    kps: List[KnowledgePointOut]
