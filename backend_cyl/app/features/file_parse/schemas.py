
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class FileParsedMetadataES(BaseModel):
    '''
    文件解析后的信息，用于构造存储进ES的数据
    '''
    id: str
    content_ltks: str
    content_with_weight: str
    content_sm_ltks: str
    important_kwd:list = []
    important_tks:list = []
    question_kwd:list = []
    question_tks:list = []

    knowledgebase_id:str               # ES索引名
    doc_id:str
    doc_name:str
    doc_name_kwd:str
    title_tks:str

    q_1024_vec:list[float]

    create_time: str = Field(default_factory=lambda: str(datetime.now()).replace("T", " ")[:19])
    create_time_flt: float = Field(default_factory=lambda: datetime.now().timestamp()) #浮点时间戳，方便排序、过滤、范围查询
    update_time: str = Field(default_factory=lambda: str(datetime.now()).replace("T", " ")[:19])


class DocumentUploadResponse(BaseModel):
    """文档上传记录响应模型"""
    id: int
    session_id: str
    document_name: str
    document_type: str
    file_size: Optional[int]
    upload_time: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SessionDocumentsResponse(BaseModel):
    """会话文档信息响应模型"""
    session_id: str
    has_documents: bool
    documents: List[DocumentUploadResponse]
    total_count: int
    
    class Config:
        from_attributes = True