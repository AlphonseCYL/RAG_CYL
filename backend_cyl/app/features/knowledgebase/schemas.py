from pydantic import BaseModel, Field


class CreateKnowledgeBaseRequest(BaseModel):
    knowledgebase_name: str = Field(..., min_length=1, max_length=255, description="知识库名称")


class KnowledgeBaseItem(BaseModel):
    knowledge_id: str = Field(..., description="知识库ID")
    user_id: str = Field(..., description="用户ID")
    knowledgebase_name: str = Field(..., description="知识库名称")
    knowledgebase_dir: str = Field(..., description="知识库目录")
    file_count: int = Field(0, description="文件数量")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")


class KnowledgeBaseListResponse(BaseModel):
    knowledgebases: list[KnowledgeBaseItem]
    status: str = Field("success", description="状态")
    message: str = Field("知识库列表加载成功", description="消息")


class CreateKnowledgeBaseResponse(BaseModel):
    '''
    创建知识库响应模型
    '''
    knowledge_id: str = Field(..., description="知识库ID")
    user_id: str = Field(..., description="用户ID")
    knowledgebase_name: str = Field(..., description="知识库名称")
    knowledgebase_dir: str = Field(..., description="知识库目录")

    status: str = Field("success", description="状态")
    message: str = Field("知识库创建成功", description="消息")



