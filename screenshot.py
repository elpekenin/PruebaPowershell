
from datos import info
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]

from selenium import webdriver
from selenium.webdriver.common.by import By

from selenium.webdriver.chrome.options import Options
options = webdriver.ChromeOptions()
options.headless = True
driver = webdriver.Chrome(options=options)

# driver = webdriver.Firefox()

scroll = lambda size: driver.execute_script('return document.body.parentNode.scroll'+size)

import boto3
bucket = boto3.resource('s3').Bucket(info.s3_bucket_name)

from os import path
import os
parse_url = lambda url: url.split('://')[1].replace("/", "").replace(".","")
image_path = lambda url: path.join(os.path.dirname(os.path.abspath(__file__)),'imagenes', f"{url}.png")

def take_screenshot(url: str) -> str:
    """
    Esta función toma una screenshot de la URL recibida y la guarda en formato PNG
    > Lo hacemos así porque el texto de las Card no se puede copiar
    > Si ya tenemos la screenshot, no la volvemos a tomar (más rápido)
    """

    #eliminamos algunos caracteres para poder guardar la imagen con la URL como nombre
    parsed_url = parse_url(url)
    #URL de la imagen en nuestro servidor
    file_url = f"https://imagenes-tfg.s3.eu-west-3.amazonaws.com/{parsed_url}"
    #ruta del archivo en el disco duro del servidor
    file_path = image_path(parsed_url)

    #si no tenemos imagen, screenshot
    if not os.path.exists(file_path):
        driver.get(url)
        #driver.set_window_size(scroll('Width'),scroll('Height'))   
        driver.find_element(By.TAG_NAME, "body").screenshot(file_path)
        driver.quit()


    #subimos el archivo a s3
    with open(file_path, 'rb') as data:
        bucket.put_object(Key=parsed_url, Body=data)

    #devolvemos un objeto Image    
    return Image(file_url, file_url)

#iteramos la base de datos para generar los archivos
for element in database:
    pass 