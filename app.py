#     --------------------Desarrollador--------------------
#     Pablo Martínez Bernal <martinezbernalpablo@gmail.com>
#     
#     ----------------------Licencia.----------------------
#     Licencia MIT [https://opensource.org/licenses/MIT]
#     Copyright (c) 2021 Pablo Martínez Bernal
# ==========================================================

# ==========================================================
#      IMPORTS
# ==========================================================

## Constantes
from datos import info

## Debug
import logging
import datetime

## Alexa Skill Kit SDK
import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from flask_ask_sdk.skill_adapter import SkillAdapter
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
from ask_sdk_model.ui import SimpleCard, StandardCard
from ask_sdk_model.ui.image import Image

## Flask
from flask import Flask, render_template, request
import json

## MongoDB
from pymongo import MongoClient

## Type hinting
from typing import Union
from collections.abc import Callable

## Decoradores
import functools

## Parecido string
from difflib  import get_close_matches

## Peticiones HTTP
from requests import get


# ==========================================================
#      CONFIGURACIÓN
# ==========================================================
logging.basicConfig(
    level=logging.DEBUG,
    filename="app.log",
    format="%(asctime)s -- %(message)s",
    datefmt="%d-%b-%y %H:%M:%S"
)

app = Flask(__name__)

database = MongoClient(info.database_ip)[info.database_name]


# ==========================================================
#      FUNCIONES
# ==========================================================

def get_data(func: Callable, cache={}, *args, **kwargs) -> Callable: 
    """
    Este decorador sirve para obtener la info del usuario a partir del handler_input
    En la caché guardaremos token:user_id para evitar hacer peticiones extra a LWA

    Al tener como valor por defecto un diccionario vacio
    > La función se queda "ligada" a la posicion de memoria donde está ese dict
    > Conforme lo vayamos editando se guarda la información aunque el valor por 
    defecto sea vacío
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Response: #creamos función decorada
        #args[0] es self porque las funciones que estamos decorando son métodos
        #args[1] es handler_input de donde sacamos la id del usuario
        # > obtenemos el token del JSON entrante
        token = args[1].request_envelope.session.user.access_token

        if token not in cache:
            #usamos el token para obtener el id del usuario con LWA
            user_id =  get(f"https://api.amazon.com/user/profile?access_token={token}").json()["user_id"] 

            #si teniamos el usuario en la caché con otro token, borramos esa entrada
            for k, v in cache.items():
                if v == user_id:
                    cache.pop(k)
                    break

            #guardamos sus datos
            cache[token] = user_id
        
        user_id = cache[token]

        #a la función decorada le pasamos los datos (un dict) como parámetro
        #será None si el usuario no está en el sistema
        return func(
            *args,
            data=database["usuarios"].find_one({"_id": user_id}, {"_id": False}),
            **kwargs,
        )
    return wrapper #devolvemos la función decorada


def check_data(func: Callable, *args, **kwargs) -> Callable:
    """
    Decorador que comprueba si un usuario se ha dado de alta en el sistema:
    > de estarlo, se llama a la función que estamos decorando
    > si no, le pedimos que se registre
    """

    @functools.wraps(func)
    @get_data #este decorador hace uso de los datos del usuario, asi que se añade ese decorador
    def wrapper(*args, **kwargs) -> Response:
        handler_input = args[1]
        data = kwargs.get("data")
        text = "Por favor, regístrate para poder usar la skill, nec esito saber qué titulación \
        cursas para poder darte información correctamente, solo tienes que decirme 'Estudio'"

        if data is None: #si no está registrado, le decimos que lo haga
            return (
                handler_input.response_builder
                    .speak(text)
                    .ask(text)
                    .set_card(SimpleCard("Regístrate", text))
                    .response
            )

        #si está registrado, se llama a la función decorada
        return func(*args, **kwargs) 
    return wrapper


def find(input: str, filtering: None, field: str = "nombre", collection: str = "asignaturas") -> str:
    """
    Esta función devuelve la cadena más parecida al input encontrada en el campo especificado
    de la colección dada
    > se pueden aplicar filtros a la query
    """
    #el valor por defecto de una función no puede ser una estructura de datos
    # > se ligaría a una dirección de memoria y terminaría dando errores

    #lo que hacemos es que el valor por defecto sea None
    # > si tenemos ese valor, lo cambiamos por un diccionario vacío
    if filtering is None: 
        filtering = {}
    
    return get_close_matches(
        input,
        #lista con todos los valores
        list([element[field] for element in database[collection].find(filtering, {field: True})]), 
        n=1, #solo queremos encontrar un valor
        cutoff=0, #no buscamos una similaridad mínima, para garantizar que se encuentra un resultado
    )[0]


# ==========================================================
#      HANDLERS
# ==========================================================

class BaseHandler(AbstractRequestHandler): 
    """Objeto base para los handlers de Amazon, evitamos repetir can_handle"""

    amazon = False
    
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type(
            "AMAZON." * self.amazon + self.__class__.__name__.split("Handler")[0]
        )(handler_input)


class CustomHandler(AbstractRequestHandler): 
    """Objeto base para los handlers de nuestros intents"""

    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name(
            self.__class__.__name__.split("Handler")[0]
        )(handler_input)


class LaunchRequestHandler(BaseHandler):
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text =  "Tengo información de: " + \
        "guías docentes, " + \
        "profesores responsables, " + \
        "horarios de clase, " + \
        "fechas de exámenes, " + \
        "contacto secretaría, " + \
        "y días festivos" + \
        "¿Qué quieres consultar?"

        return (
            handler_input.response_builder
                .speak(text)
                .ask(text)
                .set_card(SimpleCard("Bienvenid@ al asistente virtual de la UPCT", text))
                .response
        )


class LoginIntentHandler(CustomHandler):
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        #leemos y parseamos el valor del slot
        slot_value = ask_utils.request_util.get_slot(handler_input, "StudyingSlot").value
        studying = find(slot_value, field="nombre", collection="estudios")

        #TODO preguntar si estudia {studying}
        # > guardar el valor en caso afirmativo
        # > preguntar escuela y responderle estudios disponbiles


class SubjectIntentHandler(CustomHandler):
    @check_data  #para poder filtrar segun su titulación
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        studying = kwargs.get["data"]["estudios"]

        slot_value = ask_utils.request_util.get_slot(handler_input, "SubjectSlot").value
        subject = find(slot_value, filtering={"_id.id_estudios": studying})

        #obtenemos enlace de la guia docente
        url = database["asignaturas"].find_one({"nombre": subject}, {"_id": False})["guia_docente"]

        text =  f"Aquí tienes la guía docente de {subject}"
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Guía docente", text)) #TODO standardcard
                .response
        )

class TeacherIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        studying = kwargs.get["data"]["estudios"]

        slot_value = ask_utils.request_util.get_slot(handler_input, "SubjectSlot").value
        subject = find(slot_value, filtering={"_id.id_estudios": studying})

        #obtenemos el email y nombre del profesor responsable
        email = database["asignaturas"].find_one({"nombre": subject}, {"_id": False})["responsable"]
        teacher = database["profesores"].find_one({"_id": email}, {"nombre": True})["nombre"]

        text =  f"El profesor responsable de {subject} es {teacher}, te mando su mail\n{email}"
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Profesor responsable", text))
                .response
        )


class ScheduleIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        studying = kwargs.get["data"]["estudios"]

        #filtrar por curso
        year = ask_utils.request_util.get_slot(handler_input, "YearSlot").value
        logger.info(f"year slot type {type(year)}")

        image = database["horarios"].find_one({"_id": studying, "curso": year},{"imagen": True})["imagen"]

        text =  "Aquí tienes el horario"
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(StandardCard("Profesor responsable", text, image)) #TODO generar imagenes
                .response
        )


class DatesIntentHandler(CustomHandler):
    @check_data 
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        studying = kwargs.get("data")["estudios"]
        school = database["estudios"].find_one({"_id": studying}, {"escuela": True})["escuela"]

        #valor del slot
        date = ask_utils.request_util.get_slot(handler_input, "DateSlot").value
        logger.info(f"date slot type {type(date)}")

        dates = database["fechas"].find_one({"_id": data["estudios"]},{date: True})[date]

        text =  f"Los {date} son del {dates[0]} al {dates[1]}"
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard(date, text))
                .response
        )


class ContactIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        studying = kwargs.get("data")["estudios"]
        school = database["estudios"].find_one({"_id": studying}, {"escuela": True})["escuela"]

        #creamos un generador con las formas de contactar
        contact = (f"{key}: {value}" for key, value in dict(database["contacto"].find_one({"_id": school},{"_id": False})).items())

        text =  f"Las formas de contactar con la secretaría de {studying} son {', '.join(contact)}"
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard(date, text))
                .response
        )


class HelpIntentHandler(BaseHandler):
    amazon = True

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text =  "Las opciones disponibles son: asignatura, profesor \
        horario, fechas, contacto, festivos. ¿Qué quieres consultar?"
        return (
            handler_input.response_builder
                .speak(text)
                .ask(text)
                .set_card(SimpleCard("Ayuda", text))
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return (
            ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
            ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text =  "Hasta luego"
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Cerrando...", text))
                .response
        )


class FallbackIntentHandler(BaseHandler):
    amazon = True

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        speech = "Puedes decir 'Ayuda' para ver las opciones disponibles."
        reprompt = "No te entendí. Con qué puedo ayudarte?"
        return (
            handler_input.response_builder
                .speak(speech)
                .ask(reprompt)
                .response
        )


class SessionEndedRequestHandler(BaseHandler):
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # Any cleanup logic goes here.
        return (
            handler_input.response_builder
                .speak("Cerrando")
                .response
        )


class IntentReflectorHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        intent_name = ask_utils.get_intent_name(handler_input)
        text =  f"Se ha activado el intent {intent_name}."
        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Error", text))
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input: HandlerInput, exception) -> bool:
        return True

    def handle(self, handler_input: HandlerInput, exception, *args, **kwargs) -> Response:
        logger.error(exception, exc_info=True)

        text =  "No pude hacer lo que has pedido, prueba de nuevo."

        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Error", text))
                .response
        )


# ==========================================================
#      SKILL ADAPTER
# ==========================================================

skill_builder = SkillBuilder()

skill_builder.add_request_handler(LaunchRequestHandler())
skill_builder.add_request_handler(SubjectIntentHandler())
skill_builder.add_request_handler(TeacherIntentHandler())
skill_builder.add_request_handler(ScheduleIntentHandler())
skill_builder.add_request_handler(DatesIntentHandler())
skill_builder.add_request_handler(ContactIntentHandler())

skill_builder.add_request_handler(HelpIntentHandler())
skill_builder.add_request_handler(CancelOrStopIntentHandler())
skill_builder.add_request_handler(FallbackIntentHandler())
skill_builder.add_request_handler(SessionEndedRequestHandler()) 

skill_builder.add_request_handler(IntentReflectorHandler()) #último para que no sobre-escriba
skill_builder.add_exception_handler(CatchAllExceptionHandler())

skill_adapter = SkillAdapter(
    skill=skill_builder.create(),
    skill_id=info.skill_id,
    app=app
)


# ==========================================================
#      FLASK
# ==========================================================

@app.get("/") #hello world al hacer GET
def hello_world():
    return "Hello world!"

@app.post("/") #atiende peticiones POST
def invoke_skill():
    return skill_adapter.dispatch_request()

if __name__ == "__main__":
    pass   