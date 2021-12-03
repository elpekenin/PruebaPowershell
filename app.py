from datos import info

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, filename="app.log", filemode="w")

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from flask_ask_sdk.skill_adapter import SkillAdapter
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
from ask_sdk_model.ui import SimpleCard

from flask import Flask, render_template, request
import json
app = Flask(__name__)
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]

from typing import Union
from collections.abc import Callable
import functools
from difflib  import get_close_matches
from requests import get

# Funciones que nos ayudarán ======================================================================
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
            user_id =  get(f"https://api.amazon.com/user/profile?access_token={token}").json()['user_id'] 

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
            data=database["usuarios"].find_one( 
                {"_id": user_id},
                {"_id": False}
            ),
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
        data = kwargs.get('data')
        text = "Por favor, regístrate para poder usar la skill, \
        solo tienes que decirme 'Estudio' y la titulación que estás cursando"

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


def find(input: str, filtering: None, field: str = "nombre", colection: str = "asignaturas") -> str:
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
        list([element[field] for element in database[colection].find(filtering, {field: True})]), 
        n=1, #solo queremos encontrar un valor
        cutoff=0, #no buscamos una similaridad mínima, para garantizar que se encuentra un resultado
    )[0]

# Definimos los handlers ==========================================================================
# ===== Base
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

# ===== Mis handlers
class LaunchRequestHandler(BaseHandler):
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text =  "Tengo información de: " + \
        "guías docentes, " + \
        "profesores responsables, " + \
        "horarios de clase, " + \
        "días festivos, " + \
        "y fechas de exámenes." + \
        "¿Qué quieres consultar?"

        return (
            handler_input.response_builder
                .speak(text)
                .ask(text)
                .set_card(SimpleCard("Bienvenid@ al asistente virtual de la UPCT", text))
                .response
        )


class SubjectIntentHandler(CustomHandler):
    @check_data  #para poder filtrar segun su titulación
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        data = kwargs.get('data')

        #cogemos el valor del slot y lo parseamos usando la funcion de búsqueda
        subject = ask_utils.request_util.get_slot(handler_input, "SubjectSlot").value
        subject = find(subject, filtering={'_id.id_estudios': data['estudios']})

        response = database['asignaturas'].find_one({'nombre': subject}, {'_id': False})

        text =  f"Aquí tienes el enlace a la guía docente de {subject}\n\n" + \
        f"{response['guia_docente']}"

        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Guía docente", card_text))
                .response
        )

class TeacherIntentHandler(CustomHandler):
    @check_data  #para poder filtrar segun su titulación
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        data = kwargs.get('data')

        #recogemos el valor del slot y lo parseamos usando la funcion de búsqueda
        subject = ask_utils.request_util.get_slot(handler_input, "SubjectSlot").value
        subject = find(subject, filtering={'_id.id_estudios': data['estudios']})

        response = database['asignaturas'].find_one({'nombre': subject}, {'_id': False})
        email = response['responsable']

        response = database['profesores'].find_one({'_id': email},{'nombre': True})
        teacher = response['nombre']

        text =  f"El profesor responsable de {subjexct} es {teacher}, te mando su mail" + \
        f"\n\n{email}"

        return (
            handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Profesor responsable", text))
                .response
        )

#TODO Fecha examenes, dias festivos, contacto secretaria, horario

# ===== Default
class HelpIntentHandler(BaseHandler):
    amazon = True

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text =  "Las opciones disponibles son: asignatura, profesor \
        horario, fechas, contacto. ¿Qué quieres consultar?"

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


# Creamos el SkillAdapter a partir de todos los handlers ==========================================
skill_builder = SkillBuilder()

skill_builder.add_request_handler(LaunchRequestHandler())
skill_builder.add_request_handler(SubjectIntentHandler())
skill_builder.add_request_handler(ResponsableIntentHandler())

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

# Bindeamos la funcionalidad a las rutas del servidor =============================================
@app.get("/") #hello world al hacer GET
def hello_world():
    return "Hello world!"

@app.post("/") #atiende peticiones POST
def invoke_skill():
    return skill_adapter.dispatch_request()

if __name__ == "__main__":
    pass   