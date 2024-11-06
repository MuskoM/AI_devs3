from httpx import AsyncClient, Response


async def send_form(url: str, form_data: dict, follow=True):
    async with AsyncClient(follow_redirects=follow) as client:
        resp = await client.post(url, data=form_data)
        resp.raise_for_status()
        return resp.text

async def get_page(url: str):
    async with AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

async def send_dict_as_json(url: str, data: dict) -> Response:
    async with AsyncClient() as client:
        resp = await client.post(url, json=data)
        resp.raise_for_status()
        return resp

