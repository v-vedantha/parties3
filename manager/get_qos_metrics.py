
# We want to find the latencies of the packets for each service
import os
import json
import subprocess
import requests
from collections import defaultdict

JAEGER_TRACES_ENDPOINT = "http://localhost:16686/api/traces?"
# query the jaeger traces endpoint
JAEGER_TRACES_PARAMS = "&service="
JAEGER_LIMITS_PARAMS = "limit="

SERVICES = ['compose-post-service', 'home-timeline-service',
            'media-service', 'nginx-web-server', 'post-storage-service', 'social-graph-service', 'text-service', 'unique-id-service']

# SERVICE_TO_SERVER = {
#     '/wrk2-api/post/compose': 'nginx-web-server',
#     'compose_post_client': 'nginx-web-server',
#     'compose_post_server': 'compose-post-service',
#     'compose_text_client': 'compose-post-service',
#     'compose_creator_client': 'compose-post-service',
#     'compose_creator_server' :  'user-service',
#     'compose_media_client' : 'compose-post-service',
#     'compose_media_server' : 'media-service',
#     'compose_unique_id_client' : 'compose-post-service',
#     'compose_unique_id_server' : 'unique-id-service',
#     'store_post_client' : 'compose-post-service',
#     'store_post_server' : 'post-storage-service',
#     'post_storage_mongo_insert_client' : 'post-storage-service',
#     'write_user_timeline_client' : 'compose-post-service',
#     'write_user_timeline_server' : 'user-timeline-service',
#     'write_user_timeline_mongo_insert_client' : 'user-timeline-service',
#     'write_user_timeline_redis_update_client' : 'user-timeline-service',
#     'write_home_timeline_client' : 'compose-post-service',
#     'write_home_timeline_server' : 'home-timeline-service',
#     'get_followers_client' : 'home-timeline-service',
#     'get_followers_server' : 'social-graph-service',
#     'social_graph_redis_get_client' : 'social-graph-service',
#     'write_home_timeline_redis_update_client' : 'home-timeline-service',
#     'compose_urls_server' : 'url-shorten-service',
#     'url_mongo_insert_client' : 'url-shorten-service',
#     'compose_user_mentions_server' : 'user-mention-service',
#     'compose_user_mentions_memcached_get_client' : 'user-mention-service',
#     'compose_user_mentions_mongo_find_client' : 'user-mention-service'
# }

# Get the 99% latencies for each service
def get_traces(limit, service):
    """
    Returns list of all traces for a service
    """
    url = JAEGER_TRACES_ENDPOINT + JAEGER_LIMITS_PARAMS + limit + JAEGER_TRACES_PARAMS + service
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise err

    response = json.loads(response.text)
    traces = response["data"]
    return traces

traces = get_traces("1", "nginx-web-server")

# In units of us
latencies = defaultdict(list)
for trace in traces:
    for span in trace['spans']:
        operation_name = span['operationName']
        latencies[operation_name].append(span['duration'])

# Serviers
PID_TO_SERVER = {}
processes = traces[0]['processes']
for process in processes:
    name = processes[process]['serviceName']
    PID_TO_SERVER[process] = name

SERVICE_TO_PID = {}
spans = traces[0]['spans']
for span in spans:
    operation_name = span['operationName']
    pid = span['processID']
    SERVICE_TO_PID[operation_name] = pid

SERVICE_TO_SERVER = {}
for service in SERVICE_TO_PID:
    pid = SERVICE_TO_PID[service]
    server = PID_TO_SERVER[pid]
    SERVICE_TO_SERVER[service] = server

# print(SERVICE_TO_SERVER)

# for latency in latencies:
#     print(latency)
#     print(latencies[latency])
#     print(SERVICE_TO_SERVER[latency])


# Ok we have the latencies. We can find the 95% latency per service easile
SERVICE_TO_99P_LATENCY = {}
for service in SERVICE_TO_SERVER:
    specific_latency = latencies[service]
    specific_latency.sort()
    idx = int(len(specific_latency) * 0.90)
    SERVICE_TO_99P_LATENCY[service] = specific_latency[idx]

print(SERVICE_TO_99P_LATENCY)


class Node:
    def __init__(self, name):
        self.name = name
        self.parents = []
        self.children = []

    def add_parent(self, parent):
        self.parents.append(parent)

    def add_child(self, child):
        self.children.append(child)

    def __str__(self):
        return self.name + " -> " + str([SPAN_ID_TO_NODES[child].name for child in self.children])

    def __repr__(self):
        return self.name + " -> " + str([SPAN_ID_TO_NODES[child].name for child in self.children])

SPAN_ID_TO_OPERATION_NAME = {}

SPAN_ID_TO_NODES = {}

# Build the traces
for span in traces[0]['spans']:
    SPAN_ID_TO_OPERATION_NAME[span['spanID']] = span['operationName']
    operation_name = span['operationName']
    node = Node(operation_name)
    SPAN_ID_TO_NODES[span['spanID']] = node
    references = span['references']
    print(references)
    for reference in references:
        span_id = reference['spanID']
        node.add_parent(span_id)



for span in SPAN_ID_TO_NODES:
    node = SPAN_ID_TO_NODES[span]
    for parent in node.parents:
        SPAN_ID_TO_NODES[parent].add_child(span)

print(SPAN_ID_TO_NODES)

# OPERATION NAME TO SERVER that we actuall care about
OP_TO_SERVER =  {
    '/wrk2-api/post/compose' : 'nginx-web-server',
    'compose_post_server' : 'compose-post-service',
    'compose_text_server' : 'text-service',
    'compose_user_mentions_server' : 'user-mention-service',
    'compose_user_mentions_memcached_get_client' : 'memcached_user_mention',
    'compose_user_mentions_mongo_find_client' : 'mongo_user_mention',
    'compose_urls_server' : 'url-shorten-service',
    'compose_creator_server' : 'user-service',
    'compose_media_server' : 'media-service',
    'compose_unique_id_server' : 'unique-id-service',
    'store_post_server' : 'post-storage-service',
    'post_storage_mongo_insert_client' : 'mongo_post_storage',
    'write_user_timeline_server' : 'user-timeline-service',
    'write_user_timeline_mongo_insert_client' : 'mongo_user_timeline',
    'write_user_timeline_redis_update_client' : 'redis_user_timeline',
    'write_home_timeline_server' : 'home-timeline-service',
    'get_followers_server' : 'social-graph-service',
    'social_graph_redis_get_client' : 'redis_social_graph',
    'write_home_timeline_redis_update_client' : 'redis_home_timeline'
}

SERVER_TO_OP = {}
for op in OP_TO_SERVER:
    server = OP_TO_SERVER[op]
    assert server not in SERVER_TO_OP
    SERVER_TO_OP[server] = op

p = subprocess.Popen("docker ps", shell=True, stdout=subprocess.PIPE)
out, err = p.communicate()
out = out.decode()
print(out)
# Split out by lines
lines = out.split("\n")
def get_name(line):
    return line.split()[-1]

def get_id(line):
    return line.split()[0]

MY_NAME_TO_REAL_NAME = {
    'nginx-web-server' : 'socialnetwork-nginx-thrift-1',
    'compose-post-service' : 'socialnetwork-compose-post-service-1',
    'text-service' : 'socialnetwork-text-service-1',
    'user-mention-service' : 'socialnetwork-user-mention-service-1',
    'memcached_user_mention' : 'socialnetwork-user-memcached-1',
    'mongo_user_mention' : 'socialnetwork-user-mongodb-1',
    'url-shorten-service' : 'socialnetwork-url-shorten-service-1',
    'user-service' : 'socialnetwork-user-service-1',
    'media-service' : 'socialnetwork-media-service-1',
    'unique-id-service' : 'socialnetwork-unique-id-service-1',
    'post-storage-service' : 'socialnetwork-post-storage-service-1',
    'mongo_post_storage' : 'socialnetwork-post-storage-mongodb-1',
    'user-timeline-service' : 'socialnetwork-user-timeline-service-1',
    'mongo_user_timeline' :  'socialnetwork-user-timeline-mongodb-1',
    'redis_user_timeline' : 'socialnetwork-user-timeline-mongodb-1',
    'home-timeline-service' : 'socialnetwork-home-timeline-service-1',
    'social-graph-service' : 'socialnetwork-social-graph-service-1',
    'redis_social_graph' : 'socialnetwork-social-graph-redis-1',
    'redis_home_timeline' : 'socialnetwork-home-timeline-redis-1'
}

REAL_NAME_TO_MY_NAME = {v: k for k, v in MY_NAME_TO_REAL_NAME.items()}

SERVER_TO_CONTAINER_ID = { }

for line in lines:
    if len(line) == 0:
        continue
    name = get_name(line)
    container_id = get_id(line)
    if name in REAL_NAME_TO_MY_NAME:
        SERVER_TO_CONTAINER_ID[REAL_NAME_TO_MY_NAME[name]] = container_id

SERVER_TO_OS_ID = {}
for server in SERVER_TO_CONTAINER_ID:
    container_id = SERVER_TO_CONTAINER_ID[server]
    p = subprocess.Popen("docker inspect -f '{{.State.Pid}}' " + container_id, shell=True, stdout=subprocess.PIPE)
    out, err = p.communicate()
    out = out.decode()
    SERVER_TO_OS_ID[server] = out.strip()

print(SERVER_TO_OS_ID)

# Sweeeeeet baby. Finally I need something that will get the latency of each service I care about
def get_latencies_for_operation(op):
    latencies = []
    traces = get_traces("10", "nginx-web-server")
    for trace in traces:
        for span in trace['spans']:
            operation_name = span['operationName']
            if operation_name == op:
                latencies.append(span['duration']) # Once again in us

    return latencies


def get_99p_latency_for_operation(op):
    latencies = get_latencies_for_operation(op)
    latencies.sort()
    idx = int(len(latencies) * 0.90)
    return latencies[idx]

def get_99p_latency_for_server(server):
    op = SERVER_TO_OP[server]
    return get_99p_latency_for_operation(op)


def container_to_fullId(container_id):
    p = subprocess.Popen("docker inspect -f '{{.Id}}' " + container_id, shell=True, stdout=subprocess.PIPE)
    out, err = p.communicate()
    out = out.decode()
    return out

SERVER_TO_FULL_ID = {}
for server in SERVER_TO_CONTAINER_ID:
    container_id = SERVER_TO_CONTAINER_ID[server]
    SERVER_TO_FULL_ID[server] = container_to_fullId(container_id)
