from typing import List
import datetime
import xxhash
import logging

from app.features.file_parse.schemas import FileParsedMetadataES
from app.rag.nlp.model import generate_embedding
from app.rag.app.naive import chunk
from app.core.es_conn import ESConnection

logger = logging.getLogger('file_parse')

def dummy(*args, **kwargs):
    pass

############################################
#
#   批量生成嵌入向量
#   
#
############################################
def batch_generate_embeddings(
        texts: List[str], 
        batch_size: int = 10
        ) -> List[List[float]] | List[float] | None:
    '''
    批量生成文本的向量表示
    
    Args:
        texts: 文本列表
    
    Returns:
        向量列表    
    '''
    try:
        embeddings = generate_embedding(texts)
        return embeddings
    except Exception as e:
        # 处理异常情况，例如日志记录或返回默认值
        logger.error(f"批量生成向量失败: {e}")
        return []

def process_items(doc_items: List[dict], 
                  file_name: str, 
                  index_name: str
                  ) -> List[FileParsedMetadataES]:
    '''
    批量处理数据项
    
    Args:
        items: 数据项列表
        file_name: 文件名
        index_name: ES索引名称
    
    Returns:
        处理后的数据项列表    
    '''
    try:
        # 准备批处理量的数据
        texts = [item["content_with_weight"] for item in doc_items]
        # 批量生成向量
        embeddings = batch_generate_embeddings(texts)

        # 处理每个数据项，添加向量和元数据
        results = []
        for item, embedding in zip(doc_items, embeddings):# type: ignore
            # 生成chunk_id，可以使用文件名和内容的哈希值等方式
            chunk_id = xxhash.xxh64((item["content_with_weight"] + index_name).encode("utf-8")).hexdigest()
                # chunk_id示例: 
            
            # 构建要插入ES的数据项
            chunk_metadata = FileParsedMetadataES(
                id=chunk_id,
                content_ltks=item["content_ltks"],
                content_sm_ltks=item["content_sm_ltks"],
                content_with_weight=item['content_with_weight'],
                knowledgebase_id=index_name,
                doc_id=xxhash.xxh64(file_name.encode("utf-8")).hexdigest(),
                doc_name=file_name,
                doc_name_kwd=item["docnm_kwd"],
                title_tks=item["title_tks"],
                q_1024_vec=embedding
                )
            results.append(chunk_metadata)
            ## content_ltks: item["content_ltks"]
            # 含义：文本内容的粗粒度分词结果
            # 处理：使用RAG分词器进行基础分词
            # 示例：["人工智能", "是", "一门", "新兴", "技术"]
            ## content_with_weight: item["content_with_weight"]
            # 含义：原始文本内容（带权重信息）
            # 作用：保存完整的文本内容，用于显示和检索
            # 示例："人工智能是一门新兴技术，在各个领域都有广泛应用。"
            ## content_sm_ltks: item["content_sm_ltks"]
            # 含义：文本内容的细粒度分词结果
            # 处理：更详细的分词，包含更多语义信息
            # 示例：["人工", "智能", "是", "一门", "新兴", "的", "技术"]
            ## kb_id: index_name
            # 含义：知识库标识符
            # 作用：标识文档块属于哪个知识库
            # 示例："tech_documents", "company_policies"
            ## docnm_kwd: item["docnm_kwd"]
            # 含义：文档名称关键词
            # 来源：从原始文件名提取的关键词
            # 作用：用于基于文档名的检索
            ## title_tks: item["title_tks"]
            # 含义：文档标题的分词结果
            # 处理：去除文件扩展名后进行分词
            # 示例：["人工智能", "技术", "报告"]
            ## docnm: file_name
            # 含义：完整的文档文件名
            # 作用：保存原始文件名，用于溯源和显示
            # 示例："人工智能技术报告.pdf"
        return results
    except Exception as e:
        logger.error(f"process_items error: {e}")
        return []

    

def execute_insert_file_to_es(file_url: str, file_name: str, index_name: str) -> None:
    '''
    执行文档处理和插入 Elasticsearch 的函数
    Args:
        file_url: 文件URL
        file_name: 文件名
        index_name: ES索引名称
    '''
    # 1. 解析文件内容，获取文本和元数据
    documents = chunk(file_url, callback=dummy)
    '''
    documents示例:
[
    {
        "content_with_weight": "人工智能是一门新兴技术，在各个领域都有广泛应用。",
        "content_ltks": ["人工智能", "是", "一门", "新兴", "技术"],
        "content_sm_ltks": ["人工智能", "是", "一门", "新兴", "的", "技术"],
        "docnm_kwd": ["人工智能"],
        "title_tks": ["人工智能", "技术", "报告"],
    },
    ...
]
    '''
    # 2. 批量处理文档，处理为插入ES的格式
    processed_docs = process_items(documents, file_name, index_name)
    processed_docs_dict = [item.model_dump() for item in processed_docs]
    '''
    processed_docs_dict示例：
[
    {
        "id": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "content_ltks": ["人工智能", "是", "一门", "新兴", "技术"],
        "content_sm_ltks": ["人工智能", "是", "一门", "新兴", "的", "技术"],
        "content_with_weight": "人工智能是一门新兴技术，在各个领域都有广泛应用。",
    }
]
    '''
    # 3. 批量插入ES
    try:
        es_connection = ESConnection()
        es_connection.insert(documents=processed_docs_dict, indexName=index_name)
        logger.info(f"Successfully inserted {len(processed_docs_dict)} documents into ES")

    except Exception as e:
        logger.info(f"Failed to insert documents into ES: {e}")


# 测试代码
if __name__ == "__main__":
    print("")
