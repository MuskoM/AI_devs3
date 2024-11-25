import asyncio
from typing import Literal
from loguru import logger as LOG
from langfuse.openai import AsyncOpenAI
from openai.types.create_embedding_response import CreateEmbeddingResponse
from pymilvus import MilvusClient, MilvusException
from pymilvus.exceptions import ErrorCode

class EmbeddingService:
    def __init__(self, base_url=None, model='text-embedding-ada-002') -> None:
        self.client_args = {}
        if base_url:
            self.client_args['base_url'] = base_url
        self.model = model

    async def generate_embedding(self, embedding_text: str | list[str]) -> CreateEmbeddingResponse:
        async with AsyncOpenAI(**self.client_args) as ai:
            return await ai.embeddings.create(input=embedding_text, model=self.model)


class VectorService:
    TASK_TYPES = Literal['search_document', 'search_query', 'clustering', 'classification']
    def __init__(self, embedding_service: EmbeddingService, database_name: str) -> None:
        self._embedding_service = embedding_service
        self.client = MilvusClient(uri='http://100.77.242.95:19530', token='root:Milvus', db_name=database_name)

    def __ensure_collection(self, collection_name: str):
        if not self.client.has_collection(collection_name):
            raise MilvusException(code=ErrorCode.COLLECTION_NOT_FOUND, message='Collection Not Found')

    def create_collection(self, collection_name: str, dimension: int) -> bool:
        '''Create collection, 
        if collection has been created return True,
        if collection already exists return False
        '''
        if self.client.has_collection(collection_name):
            LOG.info('Collection "{}" already exists', collection_name)
            return False
        
        try:
            self.client.create_collection(collection_name, dimension, auto_id=True)
            return True
        except Exception as exc:
            LOG.error('Unable to create a collection due to an error: {}', str(exc))
            raise MilvusException(
                code=ErrorCode.UNEXPECTED_ERROR,
                message='Unable to create a collection, see logs for more details'
            )

    async def insert_into_collection(self, collection_name: str, task_type: TASK_TYPES, docs: list[str], tags: list[str] = []):
        self.__ensure_collection(collection_name)
        generate_embeddings_coro = [self._embedding_service.generate_embedding(f'{task_type}: {doc}') for doc in docs]
        vectors = await asyncio.gather(*generate_embeddings_coro)
        LOG.info('Generated embeddings for docs ', len(vectors[0].data[0].embedding))
        data = [{'vector': vector, 'uuid': 'UIDHERE', 'text': doc, 'tags': tags} for doc, vector in zip(docs,vectors)]
        self.client.insert(collection_name=collection_name, data=data)


# TESTS ====
async def test_create_embedding():
    embedding_service = EmbeddingService(base_url='http://localhost:11434/v1', model='nomic-embed-text')
    embedding_response = await embedding_service.generate_embedding('Hello There')
    assert embedding_response.model == 'nomic-embed-text'
    assert len(embedding_response.data) > 0

async def test_insert_embeddings():
    embedding_service = EmbeddingService(base_url='http://localhost:11434/v1', model='nomic-embed-text')
    vector_service = VectorService(embedding_service, 'test')
    vector_service.create_collection('test', 768)
    texts = [
        'Mary had a little lamb',
        'Its raining man',
        'Welcome Home',
    ]
    await vector_service.insert_into_collection('test','search_document', texts)
