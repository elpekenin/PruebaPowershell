from difflib  import get_close_matches
from datos import info
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]

cursor = dict(database["asignaturas"].find_one({"nombre": "Conceptos Avanzados de Internet"}, {"_id": False}))

print("\n".join(k for k in cursor.values()))