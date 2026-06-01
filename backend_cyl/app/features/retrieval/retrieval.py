
from app.rag.utils.es_conn import ESConnection
from app.rag.nlp.search_v2 import Dealer

es_connection = ESConnection()

dealer = Dealer(dataStore=es_connection)

def retrieve_content(index_name:str, user_question:str) -> list[dict]:

    # 执行搜索
    results = dealer.retrieval(
        question=user_question,
        embd_mdl=None,
        tenant_ids=index_name,
        kb_ids=None,
        page=1,
        page_size=5,
        vector_similarity_weight=0.6
    )

    # 提取chunks中的信息
    extracted_data = []

    for i,chunk in enumerate(results["chunks"], start=1):
        content_with_weight = chunk.get("content_with_weight", "N/A")
        doc_id = chunk.get('doc_id', 'N/A')
        doc_name = chunk.get('doc_name_kwd', 'N/A')
        doc_name = doc_name.split("/")[-1]

        message = {
            "id": i,
            "document_id": doc_id,
            "document_name": doc_name,
            'content_with_weight': content_with_weight,
        }

        extracted_data.append(message)

        
    return extracted_data


if __name__ == '__main__':
    res = retrieve_content(user_question="世运电路成长性如何", index_name="368300da034a49ca")
    print(res)
    
    # 将提取的数据写入到文件
    # with open("output.txt", "w", encoding="utf-8") as file:
    #     for data in extracted_data:
    #         file.write(f"content_with_weight: {data['content_with_weight']}\n")
    #         file.write(f"similarity: {data['similarity']}\n")
    #         file.write(f"vector_similarity: {data['vector_similarity']}\n")
    #         file.write(f"term_similarity: {data['term_similarity']}\n")
    #         file.write("\n")
    
    # print("结果已写入到 output.txt 文件中")