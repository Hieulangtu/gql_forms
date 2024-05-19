from typing import Any, List
import logging
import os
from pydantic import BaseModel

import logging
import logging.handlers
import socket
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s.%(msecs)03d\t%(levelname)s:\t%(message)s', 
    datefmt='%Y-%m-%dT%I:%M:%S')
SYSLOGHOST = os.getenv("SYSLOGHOST", None)
if SYSLOGHOST is not None:
    [address, strport, *_] = SYSLOGHOST.split(':')
    assert len(_) == 0, f"SYSLOGHOST {SYSLOGHOST} has unexpected structure, try `localhost:514` or similar (514 is UDP port)"
    port = int(strport)
    my_logger = logging.getLogger()
    my_logger.setLevel(logging.INFO)
    handler = logging.handlers.SysLogHandler(address=(address, port), socktype=socket.SOCK_DGRAM)
    #handler = logging.handlers.SocketHandler('10.10.11.11', 611)
    my_logger.addHandler(handler)



from fastapi import FastAPI, Request, Depends
from strawberry.fastapi import GraphQLRouter
from contextlib import asynccontextmanager

from DBDefinitions import ComposeConnectionString

## Zabezpecuje prvotni inicializaci DB a definovani Nahodne struktury pro "Univerzity"
# from gql_workflow.DBFeeder import createSystemDataStructureRoleTypes, createSystemDataStructureGroupTypes

connectionString = ComposeConnectionString()

appcontext = {}
@asynccontextmanager
async def initEngine(app: FastAPI):

    from DBDefinitions import startEngine, ComposeConnectionString

    connectionstring = ComposeConnectionString()
    makeDrop = os.getenv("DEMO", None) == "True"
    asyncSessionMaker = await startEngine(
        connectionstring=connectionstring,
        makeDrop=makeDrop,
        makeUp=True
    )

    appcontext["asyncSessionMaker"] = asyncSessionMaker

    logging.info("engine started")

    from utils.DBFeeder import initDB
    await initDB(asyncSessionMaker)

    logging.info("data (if any) imported")
    yield


from GraphTypeDefinitions import schema
from utils.sentinel import sentinel

async def get_context(request: Request):
    asyncSessionMaker = appcontext.get("asyncSessionMaker", None)
    if asyncSessionMaker is None:
        async with initEngine(app) as cntx:
            pass
        
    from utils.Dataloaders import createLoadersContext, createUgConnectionContext
    context = createLoadersContext(appcontext["asyncSessionMaker"])
    i = Item(query = "")
    # i.query = ""
    # i.variables = {}
    logging.info(f"before sentinel current user is {request.scope.get('user', None)}")
    await sentinel(request, i)
    logging.info(f"after sentinel current user is {request.scope.get('user', None)}")
    connectionContext = createUgConnectionContext(request=request)
    result = {**context, **connectionContext}
    result["request"] = request
    result["user"] = request.scope.get("user", None)
    logging.info(f"context created {result}")
    return result

app = FastAPI(lifespan=initEngine)

from doc import attachVoyager
attachVoyager(app, path="/gql/doc")

print("All initialization is done")
@app.get('/hello')
def hello(request: Request):
    headers = request.headers
    auth = request.auth
    user = request.scope["user"]
    return {'hello': 'world', 'headers': {**headers}, 'auth': f"{auth}", 'user': user}


graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context
)

class Item(BaseModel):
    query: str
    variables: dict = {}
    operationName: str = None

app.include_router(graphql_app, prefix="/gql2")

@app.get("/gql")
async def graphiql(request: Request):
    return await graphql_app.render_graphql_ide(request)


# Implementation of SLI collection with prometheus python client.
from prometheus_client import start_http_server, Counter, Histogram
from random import uniform # devel only
import time

HISTOGRAM = Histogram('request_latency_seconds', 'Latency created by processing request')

# Custom counter can be implemented in a function
#   to count only certain part of the request processing.
# But I'm using it to show the usage of labels.
c = Counter('request_count_total', 'Count of labeled requests', ['result','endpoint'])

# Labels are good to filter data while processing them,
#   events can be ignored or categorized with labels.
# Labels can also be used to tag 'bad' events and watch what degrades the service quality.
c.labels('success','/gql')
c.labels('fail','/gql')
start_http_server(8080)

@HISTOGRAM.time()
def apollo_gql_slo_dummy(t):
    time.sleep(t)
    if t > 4.7:
        c.labels('fail','/gql').inc() # increases 1 by default, .inc(NUMBER)
    else:
        c.labels('success','/gql').inc()
    return 0


from utils.sentinel import sentinel

from prometheus_client import Histogram

APOLLO_GQL_HISTOGRAM = Histogram('apollo_gql_processing_seconds', 'Time spent processing apollo_gql requests')
@APOLLO_GQL_HISTOGRAM.time()

@app.post("/gql")
async def apollo_gql(request: Request, item: Item):
    DEMOE = os.getenv("DEMO", None)
    # logging.info(f"apollo_gql DEMO {DEMOE} {type(DEMOE)}, {DEMO}")
    logging.info(f"asking sentinel for advice (is user authenticated?)")
    sentinelResult = await sentinel(request, item)
    if DEMOE == "False":
        if sentinelResult:
            return sentinelResult
        logging.info(f"sentinel test passed for query={item} for user {request.scope.get('user', None)}")
    else:
        request.scope["user"] = {"id": "2d9dc5ca-a4a2-11ed-b9df-0242ac120003"}
        logging.info(f"sentinel skippend because of DEMO mode")
    try:
        context = await get_context(request)
        logging.info(f"executing \n {item.query} \n with \n {item.variables}")
        schemaresult = await schema.execute(query=item.query, variable_values=item.variables, operation_name=item.operationName, context_value=context)
        # schemaresult = await schema.execute(query=item.query, variable_values=item.variables, context_value=context)
        # assert 1 == 0, ":)"
    except Exception as e:
        logging.info(f"error during schema execute {e}")
        return {"data": None, "errors": [f"{type(e).__name__}: {e}"]}
    
    logging.info(f"schema execute result \n{schemaresult}")
    result = {"data": schemaresult.data}
    if schemaresult.errors:
        result["errors"] = [f"{error}" for error in schemaresult.errors]
    return result

# from uoishelpers.authenticationMiddleware import BasicAuthenticationMiddleware302, BasicAuthBackend
# app.add_middleware(BasicAuthenticationMiddleware302, backend=BasicAuthBackend(
#         JWTPUBLICKEY = JWTPUBLICKEY,
#         JWTRESOLVEUSERPATH = JWTRESOLVEUSERPATH
# ))

import os
DEMO = os.getenv("DEMO", None)
assert DEMO is not None, "DEMO environment variable must be explicitly defined"
assert (DEMO == "True") or (DEMO == "False"), "DEMO environment variable can have only `True` or `False` values"
DEMO = DEMO == "True"

if DEMO:
    print("####################################################")
    print("#                                                  #")
    print("# RUNNING IN DEMO                                  #")
    print("#                                                  #")
    print("####################################################")

    logging.info("####################################################")
    logging.info("#                                                  #")
    logging.info("# RUNNING IN DEMO                                  #")
    logging.info("#                                                  #")
    logging.info("####################################################")

if not DEMO:
    GQLUG_ENDPOINT_URL = os.getenv("GQLUG_ENDPOINT_URL", None)
    assert GQLUG_ENDPOINT_URL is not None, "GQLUG_ENDPOINT_URL environment variable must be explicitly defined"
    JWTPUBLICKEYURL = os.getenv("JWTPUBLICKEYURL", None)
    assert JWTPUBLICKEYURL is not None, "JWTPUBLICKEYURL environment variable must be explicitly defined"
    JWTRESOLVEUSERPATHURL = os.getenv("JWTRESOLVEUSERPATHURL", None)
    assert JWTRESOLVEUSERPATHURL is not None, "JWTRESOLVEUSERPATHURL environment variable must be explicitly defined"
