# Embeddings
class EmbeddingManager:

    def embed_query(self, text: str) -> list[float]:
        ...

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...