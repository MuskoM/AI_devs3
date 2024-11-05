from httpx import AsyncClient


async def send_form(url: str, form_data: dict, follow=True):
    async with AsyncClient(follow_redirects=follow) as client:
        resp = await client.post(url, data=form_data)
        resp.raise_for_status()
        return resp.text

async def get_page_html(url: str):
    async with AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


