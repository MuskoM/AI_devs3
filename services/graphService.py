import json
from os import environ

from loguru import logger as LOG
from neo4j import AsyncGraphDatabase

NEO4J_PASSWORD = environ['NEO4J_PASSWORD']

async def populate_database_for_connections_task():
    with open('.cache/users.json') as users_file, open('.cache/connections.json') as connections_file:
        users_json = json.load(users_file)
        connections_json = json.load(connections_file)

        for user in users_json:
            await add_user(user['id'], user['username'])
        for connection in connections_json:
            await add_connection(connection['user1_id'], connection['user2_id'])

async def add_user(id: int, name: str):
    async with AsyncGraphDatabase.driver('neo4j://polaris5', auth=('neo4j',NEO4J_PASSWORD)) as driver:
        await driver.verify_connectivity()
        _ = await driver.execute_query(
            'CREATE (u:User {id: $id, name: $name}) ',
            id=id,
            name=name,
        )
        LOG.info('Created node for {}', name)

async def add_connection(u1_id: int, u2_id: int):
    async with AsyncGraphDatabase.driver('neo4j://polaris5', auth=('neo4j',NEO4J_PASSWORD)) as driver:
        await driver.verify_connectivity()
        _ = await driver.execute_query(
            '''
            MATCH (u1:User {id: $u1_id}), (u2:User {id: $u2_id})
            CREATE (u1)-[:KNOWS]->(u2)
            RETURN u1, u2
            ''',
            u1_id=u1_id,
            u2_id=u2_id,
        )
        LOG.info('Created connection for {} -> {}', u1_id, u2_id)

async def shortest_between_users(name: str, name_dest: str):
    async with AsyncGraphDatabase.driver('neo4j://polaris5', auth=('neo4j',NEO4J_PASSWORD)) as driver:
        return await driver.execute_query(
            '''MATCH path = shortestPath(
            (u1:User {name: $name})-[:KNOWS*1..]->(u2:User {name: $name_dest})
            ) RETURN path''',
            name=name,
            name_dest=name_dest
        )
