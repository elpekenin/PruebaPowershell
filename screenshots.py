import os
import boto3
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium import webdriver
from datos import info
from pymongo import MongoClient
from app import parse_url

database = MongoClient(info.database_ip)[info.database_name]

options = webdriver.ChromeOptions()
options.headless = True
driver = webdriver.Chrome(options=options)

bucket = boto3.resource('s3').Bucket(info.s3_bucket_name)

def scroll(size: str) -> int: 
    """Ver toda la pagina web en vez de la parte visible nada más abrir"""
    return driver.execute_script('return document.body.parentNode.scroll'+size)


def image_path(url: str) -> str: 
    """Alojamos el archivo en la subcarpeta /imagenes/"""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), #ruta script
        'imagenes', #subcarpeta
        f"{parse_url(url)}.png" #nombre archivo
    )


def take_screenshot(url: str) -> None:
    """
    Toma una screenshot de la URL recibida y la guarda en formato PNG

    > Usamos imagenes porque el texto de las Card de Alexa no se puede copiar, dar
    la preview de la página aporta algo de información y nos permite saber lo que 
    debemos encontrar, de forma que detectamos si hemos copiado mal la URL en el navegador 

    > La guardamos en el disco además de subirla a S3 para evitar hacer consultas que
    comprueben si ya tenemos la imagen, porque la cantidad de peticiones que podemos
    hacer de forma gratuita es limitada. Esto también nos permite borrar los archivos
    locales si queremos actualizar las imágenes que tenemos en S3

    > Si tenemos la imagen en disco, no hay que hacer nada

    *Este código se ejecuta en la máquina con Windows*
    """

    # ruta del archivo en el almacenamiento local
    file_path = image_path(url)

    # si no tenemos imagen en local, la tomamos
    if not os.path.exists(file_path):
        driver.get(url)

        # descomentar si se quiere hacer scroll para ver toda la web
        # lo he desactivado porque tenemos limitación de tamaño en pixeles
        # driver.set_window_size(scroll('Width'),scroll('Height'))

        driver.find_element(By.TAG_NAME, "body").screenshot(file_path)
        driver.quit()

        # una vez tenemos la imagen, la subimos a s3
        with open(file_path, 'rb') as data:
            bucket.put_object(Key=f"{parse_url(url)}.png", Body=data)


def main(): 
    """
    Para cada coleccion hacemos una query a la base de datos
    Despues, para cada documento iteramos los campos que necesitamos

    > Hacer este bucle en el orden contrario sería lento porque la query
    es mucho mas costosa que iterar el array que ya tenemos en memoria
    """

    # en este diccionario definimos todos los campos de la base de datos de los que queremos
    # tomar capturas, separados por colecciones
    url_dict = {
        "asignaturas": ["guia_docente"],
    }

    for collection in url_dict:        
        for document in database[collection].find({}, {"_id": False}):
            for field in url_dict[collection]:
                take_screenshot(document[field])


if __name__ == '__main__':
    main()
