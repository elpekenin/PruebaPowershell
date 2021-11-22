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
skill_builder = SkillBuilder()

from flask import Flask, render_template, request
import json
app = Flask(__name__)

from pymongo import MongoClient
database = MongoClient(info.database_ip)[info.database_name]

from typing import Union
from collections.abc import Callable

import functools

# Funciones que nos ayudarán ======================================================================
def user_login(user_id: str) -> Union[dict, None]:
    """Devuelve un diccionario con los datos del usuario, o None si no está registrado"""

    return database["users"].find_one(
        {"_id": user_id},
        {"_id": False}
    )
    
def check_login(func: Callable, *args, **kwargs) -> Callable: #decorador para comprobar si un usuario se ha dado de alta en el sistema
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Response:
        handler_input = args[1] #arg[0] es self, arg[1] es el handler_input
        logger.info(type(handler_input))

        # comprobamos los datos del usuario en la base de datos
        user_id = handler_input.request_envelope.session.user.user_id
        datos = user_login(user_id)

        if datos is None: #si no está registrado, le decimos que lo haga
            return (
                handler_input.response_builder
                    .speak("Por favor, regístrate para poder usar la skill, solo tienes que decirme 'Estudio' y la titulación que estás cursando")
                    .response
            )

        return func(*args, **kwargs) #si está registrado, se llama a la función decorada
    return wrapper

# Definimos los handlers ==========================================================================
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


class LaunchRequestHandler(BaseHandler):
    @check_login
    def handle(self, handler_input: HandlerInput) -> Response:
        speak_output: str =  "Bienvenido a info uni; tengo información de asignaturas, profesores, horarios y mucho más. Que quieres hacer hoy?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask(speak_output)
                .response
        )


class AsignaturaIntentHandler(CustomHandler):
    def handle(self, handler_input: HandlerInput) -> Response:
        asignatura = ask_utils.request_util.get_slot(handler_input, "AsignaturaSlot").value
        speak_output: str =  f"Información de {asignatura}, okey"

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask(speak_output)
                .response
        )


class HelpIntentHandler(BaseHandler):
    amazon: bool = True

    def handle(self, handler_input: HandlerInput) -> Response:
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

    def handle(self, handler_input: HandlerInput) -> Response:
        speak_output: str =  "Hasta luego"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class FallbackIntentHandler(BaseHandler):
    amazon: bool = True

    def handle(self, handler_input: HandlerInput) -> Response:
        speech = "No estoy seguro. Puedes decir Ayuda para ver las opciones disponibles. Qué quieres hacer?"
        reprompt = "No te entendí. Con qué puedo ayudarte?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response


class SessionEndedRequestHandler(BaseHandler):
    def handle(self, handler_input: HandlerInput) -> Response:
        # Any cleanup logic goes here.
        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input: HandlerInput):
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

    def handle(self, handler_input: HandlerInput, exception) -> Response:
        logger.error(exception, exc_info=True)

        speak_output: str =  "No pude hacer lo que has pedido, prueba de nuevo."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


# Creamos el SkillAdapter a partir de todos los handlers ==========================================
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

@app.post("/") #API haciendo POST
def invoke_skill():
    return skill_adapter.dispatch_request()

if __name__ == "__main__":
    pass   