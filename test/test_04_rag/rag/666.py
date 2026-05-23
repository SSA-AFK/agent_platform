from langchain_community.document_compressors import FlashrankRerank
rerank = FlashrankRerank()
print("FlashRank模型:", rerank.model)  # 应输出 ms-marco-MiniLM-L-6-v2