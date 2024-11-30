from datetime import datetime as dt
import json
import re
from pytz import utc

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from langfuse.decorators import observe
from langfuse.openai import langfuse_context
from loguru import logger as LOG

from exceptions import ApiException
from services.ai_devs.task_api_v3 import AiDevsAnswer, send_answer
from services.ai_devs.storeService import AIDevsStore, API_TASK_KEY
from services.ai.modelService import complete_task 
from services.web.web_interaction import send_dict_as_json, get_page
from services.prompts import PromptService

router = APIRouter(prefix='/agents', tags=['agents'])

store = AIDevsStore()
prompt_service = PromptService(label='ai_devs')


@router.get('/database')
@observe()
async def database_retrieval():
    failsafe = 10
    context_data = []
    async def send_query(url: str, query: str):
        response = await send_dict_as_json(url,data={
            'task': 'database',
            'apikey': API_TASK_KEY,
            'query': query
        })
        return response.json()

    def extract_query_from_response(resp: str):
        return resp.split('%%final_query%%')[-1].replace('\n','')
    
    def construct_context():
        return '\n\n'.join(context_data)

    def construct_prompt():
        context = construct_context()
        try:
            prompt, _ = prompt_service.get_prompt('AI_DEVS_DATABASE_SEARCH', context=context)
            return prompt
        except ApiException:
            raise

    langfuse_context.update_current_trace(session_id=f'DATABASE_{dt.now(tz=utc)}')
    secrets = store.read_task_secrets('database')
    db_url = secrets.get('database_api_url', '')
    question = 'które aktywne datacenter (DC_ID) są zarządzane przez pracowników, którzy są na urlopie (is_active=0)'
    
    query = ''
    i = 0

    while failsafe >= i:
        # Check if we can construct the query with available knowledge, if not progress with thinking
        prompt = construct_prompt()
        try:
            task_response = await complete_task(prompt, question)
        except ApiException as err:
            return JSONResponse({'err': str(err)}, status_code=500)
        LOG.info('Response from task {}', task_response)

        # Extract final_query from response (remove %%thinking%% part from response)
        query = extract_query_from_response(task_response)

        # Verify if the given prompt can answer the question
        verification_prompt, _ = prompt_service.get_prompt('AI_DEVS_DATABASE_VERIFY_QUERY', question=question)
        verification_response = await complete_task(verification_prompt, query)
        # If it can send the answer to API
        if int(verification_response) == 1:
            response = await send_query(db_url, query)
            found_ids = re.findall(r'[0-9]{4}', str(response))
            LOG.info('Final answer {}, for response {}', found_ids, response)
            return await send_answer(AiDevsAnswer(task='database', apikey=API_TASK_KEY, answer=found_ids))

        # If not, progress
        response = await send_query(db_url, query)

        # Only add to the context if the response is not null
        if response:
            context_data.append(f"Completed Query: {query}, result: {str(response['reply'])}")
        i = i + 1

# ============================

@observe()
@router.get('/loop')
async def loop_task():
    secrets = store.read_task_secrets('loop')

    # Get note about Barbara
    note_text = await get_page(url=secrets.get('note_url', ''))
    LOG.info('Fetched note {}', note_text)

    # Functions for interaction with the apis
    async def ask_about_person(name: str):
        resp =  await send_dict_as_json(
            url=secrets.get('people_api_url',''),
            data={'apikey': API_TASK_KEY, 'query': name}
        )
        return resp.json()['message'].split(' ')

    async def ask_about_places(name: str):
        resp = await send_dict_as_json(
            url=secrets.get('places_api_url',''),
            data={'apikey': API_TASK_KEY, 'query': name}
        )
        return resp.json()['message'].split(' ')

    async def verify_answer(relations:dict):
        verify_prompt = f'''
        You are given a hashmap which contains relations between people and cities:
        <relations>
        {relations}
        </relations>
        In what city is Barbara now? 
        Return only the name of the city (single word).
        If you are unable to answer return 0.
        '''
        return await complete_task(verify_prompt,'',)

    # Extract information about people and places in the note
    sys_prompt = '''
    You are responsible for extracting first names of people, and cities in the provided text.
    All names should be listed in their nominative case (Marcina => Marcin).
    In the list of people use only their first name.
    All names with polish letters should be simplified to letters from english alphabet (Rafał => Rafal, Kraków => Krakow).

    <Output_schema>
    USER: ...User message...
    AI: {"people":[], "places": []}
    </Output_schema>
    
    '''
    note_informations_raw = await complete_task(sys_prompt, note_text, local_model='gemma2:9b')
    try:
        note_informations = json.loads(note_informations_raw)
    except json.JSONDecodeError:
        # If returned json is incorrect, fix it using LLM
        fix_prompt = """Return correct JSON (don't include markdown syntax with ```) for:"""
        note_informations = json.loads(await complete_task(fix_prompt, note_informations_raw, local_model='gemma2:9b'))

    # Known people and places
    places = set()
    people = set()
    
    for person_name in note_informations['people']:
        people = {*people,*await ask_about_person(person_name)}

    for city_name in note_informations['places']:
        places = {*places,*await ask_about_places(city_name)}


    return {
        'places': places,
        'people': people,
    }
