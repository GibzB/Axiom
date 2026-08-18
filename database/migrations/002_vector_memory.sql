-- Axiom v0.1
-- Add semantic vector memory using Amazon Titan Text Embeddings V2.
-- Embedding dimension: 1024.

USE axiom;

ALTER TABLE memory_objects
ADD COLUMN IF NOT EXISTS embedding VECTOR(1024);

-- Distributed vector index for cosine similarity retrieval.
CREATE VECTOR INDEX IF NOT EXISTS idx_memory_embedding
ON memory_objects (embedding vector_cosine_ops);
