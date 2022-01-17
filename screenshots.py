
import os
from os import path
import boto3
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium import webdriver
from datos import info
from pymongo import MongoClient

database = MongoClient(info.database_ip)[info.database_name]

options = webdriver.ChromeOptions()
options.headless = True
driver = webdriver.Chrome(options=options)
# driver = webdriver.Firefox()

bucket = boto3.resource('s3').Bucket(info.s3_bucket_name)


def scroll(size): 
    """Ver toda la pagina web en vez de la parte visible nada más abrir"""
    return driver.execute_script('return document.body.parentNode.scroll'+size)

def parse_url(url): 
    """Elimina algunos caracteres de la URL para evitar errores"""
    return url.split('://')[1].replace("/", "").replace(".", "")

def image_path(url): 
    """Devuelve la ruta donde alojamos el archivo"""
    return path.join(os.path.dirname(os.path.abspath(__file__)), 'imagenes', f"{url}.png")

def take_screenshot(url: str) -> str:
    """
    Esta función toma una screenshot de la URL recibida y la guarda en formato PNG
    > Usamos imagenes porque el texto de las Card de Alea no se puede copiar
    > Si ya tenemos la imagen, la devolvemos sin volverla a tomar (más rápido)
    > La guardamos en el disco además de subirla a S3 para evitar hacer consultas que
    comprueben si ya tenemos la imagen, porque la cantidad de peticiones que podemos
    hacer de forma gratuita es limitada. Esto también nos permite borrar los archivos
    locales si queremos actualizar las imágenes que tenemos en S3

    *NOTA*: Este código se ejecuta en la máquina con Windows
    """

    # eliminamos algunos caracteres
    parsed_url = parse_url(url)
    # URL de la imagen en nuestro bucket
    file_url = f"https://imagenes-tfg.s3.eu-west-3.amazonaws.com/{parsed_url}"
    # ruta del archivo en el almacenamiento local
    file_path = image_path(parsed_url)

    # si no tenemos imagen en local, la tomamos
    if not os.path.exists(file_path):
        driver.get(url)
        # hacer scroll para ver toda la web
        # driver.set_window_size(scroll('Width'),scroll('Height'))
        driver.find_element(By.TAG_NAME, "body").screenshot(file_path)
        driver.quit()

        # subimos el archivo a s3
        with open(file_path, 'rb') as data:
            bucket.put_object(Key=parsed_url, Body=data)


# en este diccionario definimos todos los campos de la base de datos de los que queremos
# tomar capturas, separados por colecciones
url_dict = {
    "coleccion": ["campo1", "campo2"],
    "coleccion2": ["campo3", "campo4"]
}

# iteramos colecciones
for collection in url_dict:
    # iteramos los documentos de cada colección
    for document in database[collection].find_many({}, {"_id": False}):
        # iteramos los campos de los que queremos imagen
        for field in url_dict[collection]:
            take_screenshot(document[field])
