"""PDF import, chunking, embeddings (bge-m3 via llama-server) and retrieval (sqlite-vec).

Entry points: `importer.import_pdf` (doc_import handler), `retrieve.retrieve`
(quiz generation, Q&A), `store.list_docs` / `store.delete_doc`.
"""
