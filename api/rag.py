from fastapi import APIRouter, Response
from loguru import logger as LOG

from services.vectorService import EmbeddingService, VectorService

router = APIRouter(prefix='/rag', tags=['memory', 'rag'])

@router.get('/retrieve')
async def retrieve(query_string: str):
    embedding_service = EmbeddingService('http://localhost:11434/v1', 'nomic-embed-text')
    vector_service = VectorService(embedding_service, 'NexusRealm')
    return await vector_service.search_in_collection('knowledge', [query_string], output_fields=['text'])

@router.post('/remember')
async def remember(information: str):
    embedding_service = EmbeddingService('http://localhost:11434/v1', 'nomic-embed-text')
    vector_service = VectorService(embedding_service, 'NexusRealm')
    response = await vector_service.insert_into_collection('knowledge',[information])
    LOG.info('Remember response {}',response)
    return Response('Remembered')
