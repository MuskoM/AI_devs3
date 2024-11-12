import asyncio
from os import environ
from typing import Annotated, Any
import json

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import JSONResponse
from httpx import AsyncClient, HTTPStatusError
from loguru import logger as LOG
import yaml

from exceptions import ApiException
from models.ai_devs import AiDevsAnswer
from services.ai.modelService import send_once, transcribe
from services.ai_devs.task_api_v3 import send_answer
from services.data_transformers import chunker
from services.memory.cache_service import FileCacheService
from services.web.web_interaction import send_dict_as_json, send_form, get_page
from services.prompts import PromptService

class AIDevsStore:
    def __init__(self) -> None:
        self.secrets: dict[str, Any] = self.initStore()

    def initStore(self) -> dict[str, Any]:
        try:
            with open('.secrets.yml') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            LOG.error('Unable to find .secrets.yaml file, tasks from AI_Devs will not work')
            return {}

    def read_task_secrets(self, task_name: str) -> dict[str, Any]:
        task_secrets = self.secrets.get(task_name)
        if task_secrets:
            return task_secrets
        return {}

store = AIDevsStore()
prompt_service = PromptService(label='ai_devs')

def task_secrets():
    return store.read_task_secrets('corrupt_json')

TaskSecrets = Annotated[dict, Depends(task_secrets)]

Prompts = Annotated[PromptService, Depends(PromptService)]

router = APIRouter(tags=['ai_devs'], prefix='/ai_devs')

try:
    API_TASK_KEY = environ['AI_DEVS_TASK_KEY']
except KeyError:
    raise EnvironmentError('AI_DEVS_TASK_KEY not found, have you provided a key?')

@router.get('/')
async def get_tasks():
    return ('poligon', 'captcha', 'bypass_check')


@router.get('/poligon')
async def poligon_task(secrets: TaskSecrets):
    LOG.info('Executing Poligon Task')
    secrets = store.read_task_secrets('poligon')
    task_data_url = secrets.get('data_source', '')
    async with AsyncClient() as client:
        raw_data = await client.get(task_data_url)
        data_array = [t for t in raw_data.text.split('\n') if t]
        LOG.info('Fetched data and put into array {}', data_array)
        task_api_response = await send_answer(
            AiDevsAnswer(task='POLIGON', apikey=API_TASK_KEY, answer=data_array)
        )
        return task_api_response

@router.get('/captcha')
async def captcha_task(secrets: TaskSecrets):
    LOG.info('Executing Captcha Task')
    secrets = store.read_task_secrets('captcha')
    task_url = secrets.get('task_url', '')
    login = secrets.get('login', '')
    password = secrets.get('password','')
    page_html = await get_page(task_url)

    try:
        system_prompt, lf_prompt = prompt_service.get_prompt('AI_DEVS_CAPTCHA_SYSTEM_0', page_html=page_html)
    except ApiException as err:
        return JSONResponse(content=str(err), status_code=500)
    user_msg = 'What is the answer for a question on a login page?'
    # Get page
    number = await send_once([{'role': 'system', 'content': system_prompt}, {'role':'user', 'content': user_msg}], langfuse_prompt=lf_prompt)
    LOG.info('AI responded {}', number)

    successful_login_page = await send_form(task_url, {'username': login, 'password':password, 'answer': number})
    try:
        system_prompt, lf_prompt = prompt_service.get_prompt('AI_DEVS_CAPTCHA_SYSTEM', successful_login_page=successful_login_page)
    except ApiException as err:
        return JSONResponse(content=str(err), status_code=500)
    user_msg = '''
    We are looking for a flag with format {{ FLG:TEXT}}}, if its found return it.
    If any links are found return them as a list, take into account only the links that are in the <a> tags.
    If there is also something else a person can interact with return this also.
    '''
    found_info = await send_once([{'role': 'system', 'content': system_prompt}, {'role':'user', 'content': user_msg}], langfuse_prompt=lf_prompt)

    return found_info

@router.get('/bypass_check')
async def bypass_check_task(secrets: TaskSecrets):
    secrets = store.read_task_secrets('bypass_check')
    authorization_endpoint = secrets.get('task_url', '')
    try:
        system_prompt, lf_prompt = prompt_service.get_prompt('AI_DEVS_BYPASS_CHECK_SYSTEM')
    except ApiException as err:
        return JSONResponse(content=str(err), status_code=500)
    
    model_output = await send_once([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': 'send ready command'},
        ])

    LOG.info(f'Authorized {model_output}')
    try:
        authorization_result = await send_dict_as_json(authorization_endpoint, json.loads(model_output))
        authorization_json = authorization_result.json() 
        LOG.info(f'Authorized {authorization_json}')
        model_output = await send_once([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': json.dumps(authorization_json)} 
        ])
        LOG.info(f'Response after auth {model_output}')

        authorization_result = await send_dict_as_json(authorization_endpoint, json.loads(model_output))
        return authorization_result.json()
    except json.JSONDecodeError as err:
        LOG.error('Unable to parse response')
        return {'error': str(err)}
    except HTTPStatusError as err:
        LOG.error('Error occured when sending a HTTP request {}', err.response.status_code)
        return {'error': f'{err.response.status_code} - {err.request}'}

@router.get('/corrupt_json')
async def corrupt_json(secrets: TaskSecrets):
    def check_calculation(calculation: dict[str,Any]):
        def calculate_addition(addition: str) -> int:
            a, b = [int(x) for x in addition.split('+')]
            return a + b
        recalculated_answer = calculate_addition(calculation['question'])
        if calculation['answer'] != recalculated_answer:
            LOG.info('Found incorrect answer {} => {}', calculation['question'], calculation['answer'])
            obj = {**calculation}
            obj['answer'] = recalculated_answer 
            return obj
        else:
            return calculation
    
    def answer_question(test_data_instance: dict[str,Any], answers: dict[str,str]):
        if 'test' in test_data_instance:
            test_q = test_data_instance['test']
            test_q['a'] = answers[test_q['q']]
            obj = test_data_instance
            obj['test'] = test_q
            return obj
        else:
            return test_data_instance

    secrets = store.read_task_secrets('corrupt_json')
    source_json_url: str = secrets.get('source_json','')
    submit_task_url: str = secrets.get('submit_url','')
    source_json_url: str = source_json_url.replace('<apikey>', environ['AI_DEVS_TASK_KEY'])
    cache = FileCacheService() 
    
    json_file = cache.get(source_json_url)
    if not json_file:
        json_file = await get_page(source_json_url)
        cache.save(source_json_url, json_file)

    json_data = json.loads(json_file)
    
    fixed_test_data = []
    for c in json_data['test-data']:
        fixed_test_data.append(check_calculation(c))
    
    json_data['test-data'] = fixed_test_data

    test_data_chunker = chunker.BasicChunker(json_data['test-data'])
    chunks = test_data_chunker.chunk(100)

    try:
        system_prompt, lf_prompt = prompt_service.get_prompt('AI_DEVS_CORRUPT_JSON_SYSTEM')
    except ApiException as err:
        return JSONResponse(content=str(err), status_code=500)
    
    coro = [send_once([
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': json.dumps(chunk)}
            ], langfuse_prompt=lf_prompt) for chunk in chunks]
    LOG.info('Prepared {} coroutines to execute', len(coro))
    res = await asyncio.gather(*coro)
    json_responses = []
    for resp in res:
        try:
            obj = json.loads(resp)
            if obj:
                json_responses.extend(obj)
        except json.JSONDecodeError:
            LOG.error('Unable to decode {}',resp)

    LOG.info('Responses {}', json_responses)
    answers = {k['q']:k['a'] for k in json_responses}
    LOG.info('Prepared answers {}', answers)

    answered_test_data = []
    for t_d in json_data['test-data']:
        answered_test_data.append(answer_question(t_d, answers))

    json_data['test-data'] = answered_test_data
    json_data['apikey'] = API_TASK_KEY 

    task_answer_response = await send_answer(AiDevsAnswer(task='JSON',apikey=API_TASK_KEY,answer=json_data), submit_task_url)

    return task_answer_response


@router.get('/cenzura')
async def cenzura_task(secrets: TaskSecrets):
    secrets = store.read_task_secrets('cenzura')
    source_text_url: str = secrets.get('source_text', '')
    submit_task_url: str = secrets.get('submit_url','')
    source_text_url: str = source_text_url.replace('<apikey>', environ['AI_DEVS_TASK_KEY'])
    LOG.info('Fetching from {}', source_text_url)
    source_text: str = await get_page(source_text_url)
    LOG.debug('Fetched {}', source_text)
    try:
        system_prompt, lf_prompt = prompt_service.get_prompt('AI_DEVS_CENZURA_SYSTEM')
    except ApiException as err:
        return JSONResponse(content=str(err), status_code=500)

    user_prompt = source_text

    llm_response = await send_once([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ],langfuse_prompt=lf_prompt)

    return await send_answer(AiDevsAnswer(task='cenzura', apikey=API_TASK_KEY, answer=llm_response), submit_task_url)

@router.post('/mp3')
async def transcript_audio_files(audio_files: list[UploadFile]):
    secrets = store.read_task_secrets('mp3')
    submit_task_url: str = secrets.get('submit_url','')
    async def transcribe_audio(file: UploadFile):
        file_name = file.filename if file.filename else ''
        try:
            transcription = cache.get(file_name)
            if not transcription:
                transcription = await transcribe(await file.read())
                cache.save(file_name, transcription)
            return transcription
        except ApiException:
            LOG.error('Unable to process file {}',file_name)


    cache = FileCacheService()
    responses: list[str | None] = await asyncio.gather(*[
        transcribe_audio(file) for file in audio_files
    ])

    transcription_context = '\n-' + '\n-'.join([r for r in responses if r])
    try:
        system_prompt, lf_prompt = prompt_service.get_prompt('AI_DEVS_MP3_SYSTEM', evidence=transcription_context)
    except ApiException as err:
        return JSONResponse(content=str(err), status_code=500)

    user_prompt = '''
    We are looking for a man named Andrzej Maj, we have to find the address of the univeristy where he teaches his students.
    Find out the exact addresses of all matching institutions, and return those as a full addresses <STREET>, <CITY>, <COUNTRY>
    '''

    llm_response = await send_once([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ], langfuse_prompt = lf_prompt, model='gpt-4o')

    return await send_answer(AiDevsAnswer(task='mp3', apikey=API_TASK_KEY, answer=llm_response), submit_task_url)

