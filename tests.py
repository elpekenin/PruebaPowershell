from difflib  import get_close_matches
from datos import info
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]

def buscar(input: str, filtro: None, campo: str = "nombre", coleccion: str = "asignaturas") -> str:
    """
    Esta función devuelve la cadena más parecida al input encontrada en el campo especificado dentro de la colección dada, se pueden aplicar filtros a 
    la query
    """

    #el valor por defecto de una función no puede ser una estructura de datos, porque se ligaría a una dirección de memoria y daría errores
    #lo que hacemos es que el valor por defecto sea None, y si tenemos ese valor, lo cambiamos por un diccionario vacío
    if filtro is None: 
        filtro = {}
    
    return get_close_matches(
        input,
        list([elemento[campo] for elemento in database[coleccion].find(filtro, {campo: True})]), #hacemos una lista con todos los valores
        n=1, #solo devolvemos un valor
        cutoff=0, #no buscamos una similaridad mínima, para garantizar que se encuentra un resultado
    )

print(buscar("Internet", filtro={'_id.id_estudios': 2222}))