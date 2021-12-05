from difflib  import get_close_matches
from datos import info
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]
from requests import get 

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
options = webdriver.ChromeOptions()
options.headless = True
driver = webdriver.Chrome(options=options)
scroll = lambda size: driver.execute_script('return document.body.parentNode.scroll'+size)

from os import path
import os
parse_url = lambda url: url.split('://')[1].replace("/", "").replace(".","")
image_path = lambda url: path.join(os.path.dirname(os.path.abspath(__file__)),'imagenes', f"{url}.png")

def take_screenshot(url: str) -> str:
    parsed_url = parse_url(url)
    file_url = f"https://elpekenin.tk/imagenes/{parsed_url}.png"
    file_path = image_path(parsed_url)

    if not os.path.exists(file_path):
        driver.get(url)
        driver.set_window_size(scroll('Width'),scroll('Height'))   
        driver.find_element(By.TAG_NAME, "body").screenshot(file_path)
        driver.quit()

    return file_url

print(take_screenshot('https://teleco.upct.es/guia-docente/211101001'))