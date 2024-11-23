from httpx import AsyncClient, Response
from loguru import logger as LOG


async def send_form(url: str, form_data: dict, follow=True):
    async with AsyncClient(follow_redirects=follow) as client:
        resp = await client.post(url, data=form_data)
        resp.raise_for_status()
        return resp.text

async def get_page(url: str) -> str:
    LOG.info('Fetching {} page text', url)
    async with AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

async def get_http_data(url: str) -> bytes:
    LOG.info('Fetching {} page text', url)
    async with AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.read()

async def send_dict_as_json(url: str, data: dict) -> Response:
    LOG.info('Sending {} to {}', data, url)
    async with AsyncClient() as client:
        resp = await client.post(url, json=data)
        resp.raise_for_status()
        return resp

