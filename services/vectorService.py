import asyncio
from typing import Any, Literal
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
    def __init__(self, embedding_service: EmbeddingService | None, database_name: str) -> None:
        self._embedding_service = embedding_service
        self.client = MilvusClient(uri='http://100.77.242.95:19530', token='root:Milvus', db_name=database_name)

    def __ensure_collection(self, collection_name: str):
        if not self.client.has_collection(collection_name):
            raise MilvusException(code=ErrorCode.COLLECTION_NOT_FOUND, message='Collection Not Found')

    def __ensure_embedding_service_setup(self):
        if self._embedding_service is None:
            raise MilvusException(code=ErrorCode.UNEXPECTED_ERROR, message='Embedding service required, but None found')

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

    async def insert_into_collection(self, collection_name: str, docs: list[str], tags: list[str] = []):
        '''Insert documents into a collection with tags'''
        self.__ensure_collection(collection_name)
        self.__ensure_embedding_service_setup()
        generate_embeddings_coro = [self._embedding_service.generate_embedding(f'search_document: {doc}') for doc in docs] #type: ignore
        vectors = await asyncio.gather(*generate_embeddings_coro)
        LOG.info('Generated embeddings for docs {} ', len(vectors[0].data))
        data = [{'vector': vector.data[0].embedding, 'uuid': 'UIDHERE', 'text': doc, 'tags': tags} for doc, vector in zip(docs,vectors)]
        return self.client.insert(collection_name=collection_name, data=data)

    async def search_in_collection(self, collection_name: str, docs: list[str], limit = 5, output_fields: list[str] = []) -> list[list[dict[str,Any]]]:
        '''Search the collection for matching data
        Input list of docs to search,
        Returns for each doc a list of matched entries in collection
        '''
        self.__ensure_collection(collection_name)
        generate_embeddings_coro = [self._embedding_service.generate_embedding(f'search_document: {doc}') for doc in docs] #type: ignore
        vectors = await asyncio.gather(*generate_embeddings_coro)
        return self.client.search(collection_name, [embedding.data[0].embedding for embedding in vectors], limit=limit, output_fields=output_fields) #type: ignore

    async def drop_collection(self, collection_name: str):
        self.__ensure_collection(collection_name)
        self.client.drop_collection(collection_name)


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
    await vector_service.insert_into_collection('test', texts)

async def test_query_embeddings():
    embedding_service = EmbeddingService(base_url='http://localhost:11434/v1', model='nomic-embed-text')
    vector_service = VectorService(embedding_service, 'test')
    resp = await vector_service.search_in_collection('test', ['Who had an animal?', 'What is the weather?'], limit=2, output_fields=['text'])
    assert 'Mary had a little lamb' == resp[0][0]['entity']['text']
    assert 'Its raining man' == resp[1][0]['entity']['text']

# async def test_drop_collection():
#     vector_service = VectorService(None, 'test')
#     await vector_service.drop_collection('test')

