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

from flask import Flask, render_template, request
import json
app = Flask(__name__)
from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]

from typing import Union
from collections.abc import Callable
import functools
from difflib  import get_close_matches

# Funciones que nos ayudarán ======================================================================
def get_datos(func: Callable, *args, **kwargs) -> Callable: 
    """Este decorador sirve para obtener la info del usuario en nuestra base de datos, a partir del handler_input"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Response: #creamos función decorada
        #args[0] es self porque las funciones que estamos decorando son métodos, args[1] es handler_input de donde sacamos la id del usuario
        #a la función decorada le pasamos los datos (un dict) como parámetro, o None si el usuario no está en el sistema
        handler_input = args[1]

        return func(
            *args,
            datos=database["usuarios"].find_one( 
                {"_id": handler_input.request_envelope.session.user.user_id},
                {"_id": False}
            ),
            **kwargs,
        )
    return wrapper #devolvemos la función decorada


def check_datos(func: Callable, *args, **kwargs) -> Callable:
    """
    Decorador que comprueba si un usuario se ha dado de alta en el sistema, de estarlo se llama a la función que estamos decorando, y si no lo está,
    le pedimos que se registre
    """

    @functools.wraps(func)
    @get_datos #este decorador hace uso de los datos del usuario, asi que se añade ese decorador
    def wrapper(*args, **kwargs) -> Response:
        handler_input = args[1]
        datos = kwargs.get('datos')

        if datos is None: #si no está registrado, le decimos que lo haga
            return (
                handler_input.response_builder
                    .speak("Por favor, regístrate para poder usar la skill, solo tienes que decirme 'Estudio' y la titulación que estás cursando")
                    .response
            )

        #si está registrado, se llama a la función decorada pasando los datos del usuario (van en el kwargs gracias al decorador get_datos)
        return func(*args, **kwargs) 
    return wrapper

def buscar(input: str, filtro: None, campo: str = "nombre", coleccion: str = "asignaturas") -> str:
    """
    Esta función devuelve la cadena más parecida al input encontrada en el campo especificado dentro de la colección dada, se pueden aplicar filtros
    a la query
    """

    #el valor por defecto de una función no puede ser una estructura de datos, porque se ligaría a una dirección de memoria y terminaría dando errores
    #lo que hacemos es que el valor por defecto sea None, y si tenemos ese valor, lo cambiamos por un diccionario vacío
    if filtro is None: 
        filtro = {}
    
    return get_close_matches(
        input,
        list([elemento[campo] for elemento in database[coleccion].find(filtro, {campo: True})]), #hacemos una lista con todos los valores
        n=1, #solo devolvemos un valor
        cutoff=0, #no buscamos una similaridad mínima, para garantizar que se encuentra un resultado
    )[0] #devolvemos el string en vez de la lista

# Definimos los handlers ==========================================================================
# ===== Base
class BaseHandler(AbstractRequestHandler): 
    """Objeto base para los handlers de Amazon, evitamos repetir el código de la función can_handle"""

    amazon: bool = False
    
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type(
            "AMAZON." * self.amazon + self.__class__.__name__.split("Handler")[0]
        )(handler_input)


class CustomHandler(AbstractRequestHandler): 
    """Objeto base para los handlers de nuestros intents, evitamos repetir el código de la función can_handle"""

    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name(
            self.__class__.__name__.split("Handler")[0]
        )(handler_input)

# ===== Handlers
class LaunchRequestHandler(BaseHandler):
    @check_datos
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        speak_output: str =  "Bienvenido a info uni; tengo información de asignaturas, profesores, horarios y mucho más. Que quieres hacer hoy?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class AsignaturaIntentHandler(CustomHandler):
    @check_datos  #necesitamos que el usuario esté registrado para poder filtrar segun su titulación
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        datos = kwargs.get('datos')

        #recogemos el valor del slot y lo parseamos usando la funcion de búsqueda
        asignatura = ask_utils.request_util.get_slot(handler_input, "AsignaturaSlot").value
        asignatura = buscar(asignatura, filtro={'_id.id_estudios': datos['estudios']})

        speak_output: str =  f"Información de la asignatura {asignatura}, okey"

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask(speak_output) 
                .response
        )


class HelpIntentHandler(BaseHandler):
    amazon: bool = True

    @get_datos
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        speak_output: str =  "Las opciones disponibles son: Asignatura, Horario, Profesor. Qué quieres consultar?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return (
            ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
            ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    @get_datos
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        speak_output: str =  "Hasta luego"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class FallbackIntentHandler(BaseHandler):
    amazon: bool = True

    @get_datos
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        speech = "No estoy seguro. Puedes decir Ayuda para ver las opciones disponibles. Qué quieres hacer?"
        reprompt = "No te entendí. Con qué puedo ayudarte?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response


class SessionEndedRequestHandler(BaseHandler):
    @get_datos
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # Any cleanup logic goes here.
        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    @get_datos
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output: str =  f"Se ha activado el intent {intent_name}."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input: HandlerInput, exception) -> bool:
        return True

    @get_datos
    def handle(self, handler_input: HandlerInput, exception, *args, **kwargs) -> Response:
        logger.error(exception, exc_info=True)

        speak_output: str =  "No pude hacer lo que has pedido, prueba de nuevo."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


# Creamos el SkillAdapter a partir de todos los handlers ==========================================
skill_builder = SkillBuilder()
skill_builder.add_request_handler(LaunchRequestHandler())
skill_builder.add_request_handler(AsignaturaIntentHandler())
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