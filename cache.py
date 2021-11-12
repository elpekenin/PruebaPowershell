from pymongo import MongoClient
import collections
from typing import List, OrderedDict, Any
import json
import datetime

DATABASE_IP = "192.168.1.9"
DATABASE_NAME = "bot"
database = MongoClient(DATABASE_IP)[DATABASE_NAME]["multi_tasks"]  

def consultar(cache: OrderedDict, query: dict) -> List[Any]:
    if query in cache:
        # Remove and reinsert, to update order
        resultado = cache.pop(query)
        cache[query] = resultado
        return resultado

    cache[query] = list(database.find(json.loads(query), {"_id": False}))
    if len(cache) > 10:
        cache.popitem(last=False)
    return cache[query]

if __name__ == "__main__":
    cache = OrderedDict()
    query = '{"English.task":"Catch 9 pokémon"}'  

    print("Sin cache")
    print(datetime.datetime.now())
    consultar(cache, query)
    print(datetime.datetime.now())

    print("")

    print("Con cache")
    print(datetime.datetime.now())
    consultar(cache, query)
    print(datetime.datetime.now())

    