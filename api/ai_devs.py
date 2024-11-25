import asyncio
from collections import defaultdict
from os import environ
import re
from typing import Annotated, Any, Coroutine, Literal
import json
from zipfile import ZipFile

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import JSONResponse
from firecrawl import FirecrawlApp
from httpx import AsyncClient, HTTPStatusError
from loguru import logger as LOG
import yaml

from exceptions import ApiException
from models.ai_devs import AiDevsAnswer, AiDevsResponse
from services.ai.modelService import ask_about_image, complete_task, generate_image, send_once, transcribe
from services.ai_devs.task_api_v3 import send_answer
from services.data_transformers import chunker
from services.data_transformers.markdown import MarkdownLink
from services.ingestService import read_files_from_zip
from services.memory.cache_service import FileCacheService
from services.web.web_interaction import get_http_data, send_dict_as_json, send_form, get_page
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

@router.post('/robotid')
async def create_image_based_on_text():
    LOG.info('Executing robotid AI_Devs task')
    secrets = store.read_task_secrets('robotid')
    description_page_url: str = secrets.get('source_url','').replace('<apikey>', environ['AI_DEVS_TASK_KEY'])
    LOG.info('Loaded initial data desc_page_url=({})', description_page_url)
    description = json.loads(await get_page(description_page_url))['description']
    LOG.info('Loaded image description prompt ({})', description)

    image_url = await generate_image(description)
    LOG.info('Image generated can be found here=({})', image_url)
    return await send_answer(AiDevsAnswer(task='robotid', apikey=API_TASK_KEY, answer=image_url))

@router.post('/categories')
async def categories_task(archive: UploadFile):
    async def process_context_file(filename: str, file: bytes):
        LOG.info('Processing file {} ', filename)
        match check_filetype(filename):
            case 'audio':
                return filename, await transcribe(file)
            case 'text':
                return filename, file.decode()
            case 'image':
                return filename, await ask_about_image(
                    'I will OCR the text on provided image. I will only return the text that I read on the image and nothing else.',
                    file,
                    'What is written in the note tell me exactly word by word.')
            case 'unknown':
                return filename, 'Unable to read the file'

    def check_filetype(filename:str) -> Literal['image', 'text', 'audio', 'unknown']:
        ext_dict: dict[str,Literal['image', 'text', 'audio', 'unknown']] = {
            'png': 'image',
            'txt': 'text',
            'mp3': 'audio',
            '': 'unknown'
        }
        try:
            ext = filename.split('.')[1]
        except IndexError:
            LOG.warning('No type found in file {}', filename)
            ext = ''
        return ext_dict[ext]

    coroutines: list[Coroutine] = []
    LOG.info('Executing categories AI_Devs task')
    zip = ZipFile(archive.file, 'r')
    LOG.info('Loaded archive {} with files: [{}]', zip.filename ,zip.namelist())
    for file in zip.filelist:
        file_handle = zip.open(file, 'r')
        coroutines.append(process_context_file(file.filename, file_handle.read()))
        file_handle.close()
    zip.close()

    LOG.info('Created {} coroutines to execute', len(coroutines))
    results = await asyncio.gather(*coroutines)

    LOG.info('Context created {}', results)

    async def categorize_information(data: str, filename: str):
        sys_prompt = '''
        I'm responsible discovering if the data provided contains information about:
        - hardware malfunctions
        - people that got captured

        If you give me any data I will think about the content of the data:
        - What subjects are mentioned? (people, hardware, machines)
        - What is described? (hardware, software, people, machines)
        - Who made the note, was it done by a human or machine?

        Based on those criteria I will assign the labels.

        <Rules>
        - Software changes don't count towards hardware
        - Think if the note describes people captured if yes, then assign people label
        - If information mentions clues about people location assign people label but ONLY if the note is done by a machine.
        </Rules

        Result of my reasoning will be included in **thinking** section.
        My final answer will occur after **final_answer**, which will be the last section in the answer.

        The single word provided after **final_answer** is a category of information provided.
        Available categories:
        - people
        - hardware
        - other
        Give me some information you want me to categorize.

        <Example>
        **thinking**
        <Here is the thinking process>
        **final_answer**
        <category>
        </Example>
        '''
        return filename, await complete_task(sys_prompt,data, model='gpt-4o')

    coroutines = [categorize_information(context, filename) for filename, context in results]
    results: list[tuple[str,str]] = await asyncio.gather(*coroutines)
    LOG.info('Categorized data {}', results)
    categorized_files = defaultdict(lambda: [])
    for file, resp in results:
        resp_label = resp.split('**final_answer**')[1].strip()
        if resp_label != 'other':
            categorized_files[resp_label].append(file)

    return await send_answer(AiDevsAnswer(task='kategorie', apikey=API_TASK_KEY, answer=categorized_files))

@router.get('/arxiv')
async def arxiv():
    secrets = store.read_task_secrets('arxiv')
    base_url = secrets.get('base_url', '')
    article_url = secrets.get('source_url','')
    questions_url = secrets.get('questions_url','').replace('<apikey>',API_TASK_KEY)
    firecrawl_app = FirecrawlApp(api_key='test', api_url='http://polaris5:3002')

    article_context = firecrawl_app.scrape_url(article_url)
    questions = firecrawl_app.scrape_url(questions_url)
    string_chunker = chunker.StringChunker(article_context['markdown'])

    paragraphs = string_chunker.chunk_by_regex(r'\n[-=]+')
    sections = []
    next_title = None
    for paragraph in paragraphs:
        output_p = ''
        if next_title:
            output_p = f'{next_title}\n\n'

        *paragraph, next_title = paragraph.split('\n\n')

        sections.append(output_p + ''.join(paragraph))

    # If there is a leftover string append it to the last section
    if next_title:
        sections[-1] = sections[-1] + '\n' + next_title

    # Remove empty sections
    sections: list[str]  = [s for s in sections if s]

    sections_with_links = []
    # Extract all links from each section and replace them with a placeholder
    for section in sections:
        section_text = section
        links = {}
        found_links = re.findall(r'!\[\]\(https:\/\/[^\s]+\)|\[[^\]]+\]\([^\s]+\)', section)
        if found_links:
            LOG.info('Found links {}', found_links)
            for link_id, link in enumerate([l for l in found_links]):
                link_label = f'$link_{link_id}$'
                section_text = section_text.replace(link, link_label)
                links[link_label] = link

        sections_with_links.append({
            'body': section_text,
            'links': links
        })

    async def get_context_from_data(link: MarkdownLink):
        system_prompt = '''
        Jesteś odpowiedzialny za opisanie co zostało przedstawione na zdjęciu, 
        opisz wyróżniające się obiekty oraz całą scenę widoczną na zdjęciu,
        jeżeli jest na nim coś nietypowego również o tym wspomnij.
        Jeżeli zdjęcie zawiera jakiś tekst zacytuj go nie zmieniając treści.
        Nie skupiaj się na stylu zdjęcia.
        '''
        data = await get_http_data(link.url)
        LOG.info('Responded with some data {}', data[:20])
        match link.resource_type:
            case 'mp3':
                return await transcribe(data)
            case 'png':
                return await ask_about_image(system_prompt, data, 'Zdjęcie: ')

    # Iterate over links in the sections to get the context for each using LLM
    for l_section in sections_with_links:
        if 'links' in l_section:
            for link_id, link in l_section['links'].items():
                md_link = MarkdownLink(link)

                if md_link.is_relative():
                    md_link = MarkdownLink(f'[]({base_url}/{md_link.url})')

                context = await get_context_from_data(md_link)
                LOG.info('Got context for {}: {}', link, context)
                l_section['body'] = l_section['body'].replace(link_id, f'<Załącznik/>{context}</Załącznik>')

    full_context = '\n\n'.join([section['body'] for section in sections_with_links])

    system_task_prompt = f'''
    You are responsible for answering asked questions, you have to use the provided context, all the answers are there.
    The only way for you to respond is in a JSON format. Answer each question with one concise sentence.
    Follow defined response format. Think about the answer before answering, there might be trick questions.
    Tag <Załącznik> describes the attachments included in the document, text around this tag will probably reference the attachment so keep this in mind. Photo of a tower was done in Kraków. The photo of a cake is in fact a "pizza z ananasem"

    <Context>
    {full_context}
    </Context>
    ''' + '''
    <Response format>
    {
    "01": "krótka odpowiedź w 1 zdaniu",
    "02": "krótka odpowiedź w 1 zdaniu",
    "03": "krótka odpowiedź w 1 zdaniu",
    "NN": "krótka odpowiedź w 1 zdaniu"
    }
    </Response format>
    '''
    response = await complete_task(system_task_prompt,questions['markdown'], model='gpt-4o-mini')

    LOG.info('Answered questions {}', response)

    answer_resp = await send_answer(AiDevsAnswer(task='arxiv', apikey=API_TASK_KEY, answer=json.loads(response)))

    return answer_resp
        

@router.post('/documents')
async def documents(reports_archive: UploadFile, facts_archive: UploadFile):
    # Get reports for which tags will be generated
    reports = read_files_from_zip(reports_archive.file, ['txt'])

    # Get facts, those information will be put into context to help assign tags for reports
    facts = read_files_from_zip(facts_archive.file, ['txt'])

    # Summarize facts and reports, which will be later used in context to assign tags
    system_prompt = '''
    I'm responsible for extracting important information from the text you'll give me.
    First I will identify any entities mentioned in the text.
    As a next step I will extract important information about each entity.
    Lastly, I will review created lists by finding the source of the information in base text and if the information doesn't make sense as a separate entity I will fix it.
    For example: 
    She maried Alexander Ragorski - who did? The information is missing a subject.
    Correct fact is Fiona Green maried Alexander Ragorski - Now even if we don't have a base text we have the important information. 

    All previous steps will be put under **thinking** section.
    Based on the **thinking** section I will create a list of facts that will be put under **final_answer** section. Those facts will be used later in other tasks. If there is no data in the file to summarize return "No important information found" in **final_answer** section

    <Rules>
    - I will think out loud why the decision was made,
    - For each fact I will give the source in base text,
    - If a fact loses information without a context it's badly written and needs fixing,
    - Sources should be provided in the **thinking** section and not as a final answer,
    </Rules>

    <Example_output>
    **thinking**
    <Here I describe my thinking process>
    **final_answer**
    <Here I will put the FINAL list of facts>
    </Example_output>
    '''

    summarization_coroutines = [complete_task(system_prompt, content.decode()) for _, content in [*facts,*reports]]
    summarization_results = await asyncio.gather(*summarization_coroutines)
    LOG.info('Summarization results {}', summarization_results)

    # Remove thinking sections from each response
    cleaned_summarizations = [summary.split('**final_answer')[-1] for summary in summarization_results]
    LOG.info('Cleaned summarizations {}', cleaned_summarizations)

    # Put together all the facts from different sources
    system_prompt = '''
    You are a system responsible for putting together information about different people, events and places.
    Given some data you will identify what entities occur in the data and organize them in MARKDOWN format.
    For each entity describe it's relation to the other entities in the data if such relation can be made.
    
    <Rules>
    - I'm precise and diligent
    - I won't change the names of enities
    - If a relation between two entities can be found I will decribe it
    - I output only in MARKDOWN format without surrounding back ticks (`)
    </Rules>

    <Example>
    Input: Tom Green was spotted on campus of MIT on monday. Meanwhile on the same campus Hank Blue was reading a book about Physics.
    AI:
    ## Tom Green
    - Was on MIT campus on monday

    ## Hank Blue
    - Was on MIT campus on monday
    - Read a book about physics

    ## Relations
    - Tom Green and Hank Blue were on the same campus on Monday

    '''

    finalized_context = await complete_task(system_prompt, '\n'.join(cleaned_summarizations))
    LOG.info('Finalized context {}', finalized_context)

    # Main task, responsible for generating labels for each of the reports
    system_prompt = f'''
    I'm responsible for extracting keywords and metadata for reports provided. I will think about the events, people, places and animals mentioned in the report. If a person is mentioned in the report get ALL the information about that person and list it out, based on the extracted information about a person generate additional labels describing the person that was mentioned in the report. DON'T OMIT ANY DETAILS, they all might be relevant. All this process should be described in **thinking** section. I will think step by step.
    Based on the previous process I will generate labels for the report that will encompase the situation described in the report and the connected insights. Final answer will be put in the **final_answer** section as a list of tags.

    <Rules>
    - All labels will be in Polish
    - All labels will be written in their denominator form
    - Use context to extend labels
    - Tags will be provided as a list
    - List should be a string
    </Rules>

    </Help>
    There are some topics that you should watch for:
    - animals,
    - teachers,
    - programmers, software developers, technical people
    - sectors where something happened
    </Help>

    <Context>
    {finalized_context}
    </Context>

    <Example>
    User: <Report>
    AI: "nauczyciel, porwanie, Aleksander Ragowski"

    User: <Report>
    AI: "dokument, odcisk palca, aresztowanie"
    </Example>
    '''

    LOG.info('System prompt {}', system_prompt)
    label_files_coro = [complete_task(system_prompt,file_name + '\n-----' + report_content.decode() + '\n\n') for file_name, report_content in reports]
    label_file_names = [file_name for file_name, _ in reports]
    result_labeled_files = await asyncio.gather(*label_files_coro)

    LOG.info('Responses {}', result_labeled_files)

    # Send answer
    answer_result = await send_answer(AiDevsAnswer(task='dokumenty', apikey=API_TASK_KEY, answer={file_name: tags.split('**final_answer**')[-1] for file_name, tags in zip(label_file_names, result_labeled_files)}))
    return answer_result
