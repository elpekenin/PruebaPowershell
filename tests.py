from difflib  import get_close_matches
from datos import info
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]
from requests import get 

datos = {
    "peke": "hola",
    "afoasd": 3
}

for k,v in datos.items():
    print(k, v)
    if(v == "hola"):
        datos.pop(k)
        break

print(datos)