"""ChromaDB vector store interface for code embeddings."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


class VectorStore:
    """Interface to ChromaDB for storing and retrieving code embeddings."""

    def __init__(self, host: str = "chromadb", port: int = 8000, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize ChromaDB client.

        Args:
            host: ChromaDB host
            port: ChromaDB port
            embedding_model: Sentence transformer model name
        """
        self.host = host
        self.port = port
        self.embedding_model = embedding_model

        # Initialize ChromaDB client
        try:
            self.client = chromadb.HttpClient(
                host=host,
                port=port,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"Connected to ChromaDB at {host}:{port}")

            # Test connection
            self.client.heartbeat()
            logger.info("ChromaDB heartbeat successful")

        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise

        # Initialize embedding function
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        logger.info(f"Initialized embedding function: {embedding_model}")

    def create_collection(self, collection_name: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """Create or get a ChromaDB collection.

        Args:
            collection_name: Name of the collection
            metadata: Optional metadata for the collection

        Returns:
            ChromaDB collection object
        """
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                metadata=metadata or {}
            )
            logger.info(f"Created/retrieved collection: {collection_name}")
            return collection
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a ChromaDB collection.

        Args:
            collection_name: Name of the collection

        Returns:
            True if successful
        """
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False

    def add_chunks(
        self,
        collection_name: str,
        chunks: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """Add code chunks to a collection with embeddings.

        Args:
            collection_name: Name of the collection
            chunks: List of chunk dictionaries with 'code' and metadata
            batch_size: Number of chunks to process at once

        Returns:
            Number of chunks added
        """
        collection = self.create_collection(collection_name)

        total_added = 0

        # Process in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []

            for idx, chunk in enumerate(batch):
                # Generate unique ID
                chunk_id = f"{collection_name}_{i + idx}_{chunk.get('name', 'unknown')}"
                ids.append(chunk_id)

                # Document is the code content
                documents.append(chunk['code'])

                # Metadata (excluding the code itself to avoid duplication)
                metadata = {
                    'file_path': chunk.get('file_path', ''),
                    'chunk_type': chunk.get('chunk_type', 'unknown'),
                    'name': chunk.get('name', 'unknown'),
                    'language': chunk.get('language', 'unknown'),
                    'start_line': chunk.get('start_line', 0),
                    'end_line': chunk.get('end_line', 0),
                    'line_count': chunk.get('line_count', 0),
                    'char_count': chunk.get('char_count', 0),
                    'token_count_estimate': chunk.get('token_count_estimate', 0),
                    'is_uncommitted': chunk.get('is_uncommitted', False),
                    'commit_hash': chunk.get('commit_hash', ''),
                    'is_partial': chunk.get('is_partial', False),
                    'part_number': chunk.get('part_number', 0),
                    'parent_chunk': chunk.get('parent_chunk', ''),
                }

                # Convert all values to strings (ChromaDB metadata requirement)
                metadatas.append({k: str(v) for k, v in metadata.items()})

            try:
                # Add batch to collection
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                total_added += len(batch)
                logger.info(f"Added batch {i // batch_size + 1}: {len(batch)} chunks to {collection_name}")

            except Exception as e:
                logger.error(f"Failed to add batch to {collection_name}: {e}")
                raise

        logger.info(f"Successfully added {total_added} chunks to {collection_name}")
        return total_added

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query a collection for similar code chunks.

        Args:
            collection_name: Name of the collection
            query_text: Query text
            n_results: Number of results to return
            where: Metadata filter (e.g., {"language": "python"})
            where_document: Document content filter

        Returns:
            Dictionary with query results
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=['documents', 'metadatas', 'distances']
            )

            logger.info(f"Query returned {len(results['ids'][0])} results from {collection_name}")
            return results

        except Exception as e:
            logger.error(f"Failed to query collection {collection_name}: {e}")
            raise

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics for a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            count = collection.count()

            return {
                'name': collection_name,
                'count': count,
                'metadata': collection.metadata
            }

        except Exception as e:
            logger.error(f"Failed to get stats for {collection_name}: {e}")
            return {'name': collection_name, 'count': 0, 'error': str(e)}

    def update_chunk(
        self,
        collection_name: str,
        chunk_id: str,
        code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a specific chunk in the collection.

        Args:
            collection_name: Name of the collection
            chunk_id: ID of the chunk to update
            code: Updated code content (optional)
            metadata: Updated metadata (optional)

        Returns:
            True if successful
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            update_data = {'ids': [chunk_id]}

            if code is not None:
                update_data['documents'] = [code]

            if metadata is not None:
                # Convert all values to strings
                update_data['metadatas'] = [{k: str(v) for k, v in metadata.items()}]

            collection.update(**update_data)
            logger.info(f"Updated chunk {chunk_id} in {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update chunk {chunk_id} in {collection_name}: {e}")
            return False

    def delete_chunks(
        self,
        collection_name: str,
        chunk_ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Delete chunks from a collection.

        Args:
            collection_name: Name of the collection
            chunk_ids: List of chunk IDs to delete (optional)
            where: Metadata filter for deletion (optional)

        Returns:
            True if successful
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            if chunk_ids:
                collection.delete(ids=chunk_ids)
                logger.info(f"Deleted {len(chunk_ids)} chunks from {collection_name}")
            elif where:
                collection.delete(where=where)
                logger.info(f"Deleted chunks matching filter from {collection_name}")
            else:
                logger.warning("No deletion criteria provided")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to delete chunks from {collection_name}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List all collections in ChromaDB.

        Returns:
            List of collection names
        """
        try:
            collections = self.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists.

        Args:
            collection_name: Name of the collection

        Returns:
            True if collection exists
        """
        try:
            self.client.get_collection(name=collection_name)
            return True
        except Exception:
            return False

    def clear_collection(self, collection_name: str) -> bool:
        """Clear all data from a collection without deleting it.

        Args:
            collection_name: Name of the collection

        Returns:
            True if successful
        """
        try:
            # Delete and recreate collection
            self.delete_collection(collection_name)
            self.create_collection(collection_name)
            logger.info(f"Cleared collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection {collection_name}: {e}")
            return False
