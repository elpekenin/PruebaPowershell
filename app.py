#     --------------------Desarrollador--------------------
#     Pablo Martínez Bernal <martinezbernalpablo@gmail.com>
#
#     ----------------------Licencia.----------------------
#     Licencia MIT [https://opensource.org/licenses/MIT]
#     Copyright (c) 2021 Pablo Martínez Bernal
# ==========================================================

# Información
from datos import info

# Debug
import logging

# Alexa Skill Kit SDK
import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from flask_ask_sdk.skill_adapter import SkillAdapter
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
from ask_sdk_model.ui import SimpleCard, StandardCard
from ask_sdk_model.ui.image import Image

# Flask
from flask import Flask, render_template, request
import json

# MongoDB
from pymongo import MongoClient

# Type hinting
from typing import Union, Dict
from collections.abc import Callable

# Decoradores
import functools

# Parecido string
from difflib import get_close_matches

# Peticiones HTTP
from requests import get


# ==========================================================
#      CONFIGURACIÓN
# ==========================================================
logging.basicConfig(
    level=logging.DEBUG,
    filename="app.log",
    format="%(asctime)s -- %(message)s",
    datefmt="%d/%b/%y %H:%M:%S", 
    filemode="w"
)

app = Flask(__name__)

database = MongoClient(info.database_ip)[info.database_name]


# ==========================================================
#      FUNCIONES
# ==========================================================

def get_user_id(handler_input: HandlerInput, cache: Dict[str, str] = {}):
    """
    En la caché guardaremos token:user_id para evitar hacer peticiones extra a LWA
    Al tener como valor por defecto un diccionario vacío
    > La función se queda "ligada" a la posicion de memoria donde está ese dict
    > Conforme lo vayamos editando se guarda la información aunque el valor por 
    defecto sea vacío
    """

    token = handler_input.request_envelope.session.user.access_token

    if token not in cache:
            user_id = get(f"https://api.amazon.com/user/profile?access_token={token}").json()["user_id"]

            # si teníamos el usuario en la caché con otro token, borramos esa entrada
            for k, v in cache.items():
                if v == user_id:
                    cache.pop(k)
                    break

            # guardamos
            cache[token] = user_id

    return cache[token] #devolvemos el id

def get_data(func: Callable, *args, **kwargs) -> Callable:
    """Este decorador sirve para obtener la info del usuario a partir del handler_input"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Response:  # creamos función decorada
        # args[0] es self porque las funciones que estamos decorando son métodos
        # args[1] es handler_input de donde sacamos la id del usuario
        # > obtenemos el id a partir del JSON entrante
        user_id = get_user_id(args[1])
        # a la función decorada le pasamos los datos (un dict) como parámetro
        # será None si el usuario no está en el sistema
        return func(
            *args,
            data=database["usuarios"].find_one({"_id": user_id}, {"_id": False}),
            **kwargs,
        )
    return wrapper  # devolvemos la función decorada


def check_data(func: Callable, *args, **kwargs) -> Callable:
    """
    Decorador que comprueba si un usuario se ha dado de alta en el sistema:
    > de estarlo, se llama a la función que estamos decorando
    > si no, le pedimos que se registre
    """

    @functools.wraps(func)
    @get_data  # este decorador hace uso de los datos del usuario, asi que se añade ese decorador
    def wrapper(*args, **kwargs) -> Response:
        handler_input = args[1]
        data = kwargs.get("data")
        text = "Por favor, regístrate para poder usar la skill, nec esito saber qué titulación \
        cursas para poder darte información correctamente, solo tienes que decirme 'Registro'"

        if data is None:  # si no está registrado, le decimos que lo haga
            return (
                handler_input.response_builder
                .speak(text)
                .set_card(SimpleCard("Regístrate", text))
                .response
            )

        # si está registrado, se llama a la función decorada
        return func(*args, **kwargs)
    return wrapper


def find(input_str: str, filtering = None, field: str = "nombre", collection: str = "asignaturas") -> str:
    """
    Esta función devuelve la cadena más parecida al input encontrada en el campo especificado
    de la colección dada
    > se pueden aplicar filtros a la query
    """

    # el valor por defecto de una función no puede ser una estructura de datos
    # > se ligaría a una dirección de memoria y terminaría dando errores
    # lo que hacemos es que el valor por defecto sea None
    # > si tenemos ese valor, lo cambiamos por un diccionario vacío
    if filtering is None:
        filtering = {}

    return get_close_matches(
        input_str,
        # lista con todos los valores
        list((element[field] for element in database[collection].find(filtering, {field: True}))), # !!
        n=1,  # solo queremos un valor
        cutoff=0,  # no buscamos una similaridad mínima, para garantizar encontrar resultado
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
    """Objeto base para nuestros intents"""

    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name(
            self.__class__.__name__.split("Handler")[0]
        )(handler_input)


class LaunchRequestHandler(BaseHandler):
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text = "Tengo información de: " + \
            "guías docentes, " + \
            "profesores responsables, " + \
            "horarios de clase, " + \
            "fechas de exámenes, " + \
            "contacto de secretaría " + \
            "y días festivos" + \
            "¿Qué quieres consultar?"

        return (
            handler_input.response_builder
            .set_should_end_session(False) # para que no se cierre la skill
            .speak(text)
            .set_card(SimpleCard("Bienvenid@ al asistente virtual de la UPCT", text))
            .response
        )


class SignUpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        # comprobamos si el nombre del intent coincide o si hay atributos de sesion
        # > estos atributos solo los usamos para el estado de conversación del intent
        return (
            ask_utils.is_intent_name("SignUpIntent")(handler_input) or
            (handler_input.attributes_manager.session_attributes != {})
        )

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # usamos el atributo para controlar el estado de la conversacion
        attributes = handler_input.request_envelope.session.attributes
        logging.info("====== Atributos ======")
        logging.info(attributes)

        card_title = "Registro"

        # si no hay estado, le preguntamos al usuario su escuela
        if attributes == {}:
            # creamos el atributo de estado
            handler_input.attributes_manager.session_attributes["estado"] = "Escuela"
            # obtenemos el listado de escuelas
            schools = (school["_id"] for school in database["secretarias"].find({}, {}))

            text = f"Las distintas escuelas son: {', '.join(schools)}, ¿en cuál estudias? \
                Por favor, contesta diciendo 'Estudio en ...'" 
            return (
                handler_input.response_builder
                .set_should_end_session(False)
                .speak(text)
                .set_card(SimpleCard(card_title, text))
                .response
            )
        
        # si nos dice su escuela, le preguntaremos por su titulación
        if attributes["estado"] == "Escuela":
            # actualizamos el estado
            handler_input.attributes_manager.session_attributes["estado"] = "Estudio"
            # leemos y parseamos la escuela
            slot_value = ask_utils.request_util.get_slot(handler_input, "TextSlot").value
            school = find(slot_value, collection="secretarias", field="_id")
            # obtenemos los estudios de la escuela
            studies = (study["nombre"] for study in database["estudios"].find({"escuela": school}, {"nombre": True}))

            text = f"Los estudios en la escuela {school} son: {', '.join(studies)}, ¿cual es el tuyo? \
                Por favor, contesta 'Estudio ....'"
            return (
                handler_input.response_builder
                .set_should_end_session(False)
                .speak(text)
                .set_card(SimpleCard(card_title, text))
                .response
            )

        # para acabar el registro, borramos el estado y guardamos los estudios del usuario
        handler_input.attributes_manager.session_attributes.pop("estado")
        # leer y parsear
        slot_value = ask_utils.request_util.get_slot(handler_input, "TextSlot").value
        study_name = find(slot_value, collection="estudios")
        study = database["estudios"].find_one({"nombre": study_name},{})["_id"]
        # guardamos la informacion del usuario
        user_id = get_user_id(handler_input)
        try: 
            database["usuarios"].insert_one({"_id": user_id, "estudios": study})

        # si insertar la información da error es porque el usuario ya está en el sistema, actualizamos
        except Exception:
            database["usuarios"].update_one({"_id": user_id}, {"$set": {"estudios": study}})

        text = f"Vale, he registrado que estudias {study_name}({study}), si en algún momento quieres editar \
            esta información, puedes repetir el proceso de registro"          
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
            .response
        )


class SubjectIntentHandler(CustomHandler):
    @check_data  # para poder filtrar segun su titulación
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # datos del usuario
        studying = kwargs.get["data"]["estudios"]
        # datos del slot
        slot_value = ask_utils.request_util.get_slot(handler_input, "SubjectSlot").value
        subject = find(slot_value, filtering={"_id.id_estudios": studying})
        # obtenemos enlace de la guia docente
        url = database["asignaturas"].find_one({"nombre": subject}, {"_id": False})["guia_docente"]

        text = f"Aquí tienes la guía docente de {subject}, {url}"
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
            .set_card(SimpleCard("Guía docente", text))  # TODO standardcard
            .response
        )


class TeacherIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # user
        studying = kwargs.get["data"]["estudios"]
        # slot
        slot_value = ask_utils.request_util.get_slot(handler_input, "SubjectSlot").value
        subject = find(slot_value, filtering={"_id.id_estudios": studying})
        # email y nombre del profesor
        email = database["asignaturas"].find_one({"nombre": subject}, {"_id": False})["responsable"]
        teacher = database["profesores"].find_one({"_id": email}, {"nombre": True})["nombre"]

        text = f"El profesor responsable de {subject} es {teacher}, aquí tienes su mail: {email}"
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
            .set_card(SimpleCard("Profesor responsable", text))
            .response
        )


class ScheduleIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # user
        studying = kwargs.get["data"]["estudios"]
        # slot
        year = ask_utils.request_util.get_slot(handler_input, "YearSlot").value # es int
        # imagen del horario
        image = database["horarios"].find_one({"_id": studying, "curso": year}, {"imagen": True})["imagen"]

        text = f"Aquí tienes el horario de {year}º de {studying}"
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
            .set_card(StandardCard("Horario", text, image))  # TODO generar imagenes
            .response
        )


class DatesIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # user
        studying = kwargs.get("data")["estudios"]
        school = database["estudios"].find_one({"_id": studying}, {"escuela": True})["escuela"]
        # slot
        date = ask_utils.request_util.get_slot(handler_input, "DateSlot").value
        logging.info(f"date slot type {type(date)}")
        # información
        dates = database["fechas"].find_one({"_id": studying}, {date: True})[date]

        text = f"Los {date} son del {dates[0]} al {dates[1]}"
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
            .set_card(SimpleCard(date, text))
            .response
        )


class ContactIntentHandler(CustomHandler):
    @check_data
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        studying = kwargs.get("data")["estudios"]
        school = database["estudios"].find_one({"_id": studying}, {"escuela": True})["escuela"]

        # creamos un generador con las formas de contactar
        contact = (f"{k.capitalize()} ({v})" 
        for k, v in dict(database["secretarias"].find_one({"_id": school}, {"_id": False})).items())

        nl = "\n"
        text = f"Las formas de contactar con la secretaría de {school} son {nl.join(contact)}"
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
            .set_card(SimpleCard("Contacto", text))
            .response
        )


class HelpIntentHandler(BaseHandler):
    amazon = True

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        text = "Las opciones disponibles son: asignatura, profesor \
        horario, fechas, contacto, festivos. ¿Qué quieres consultar?"
        return (
            handler_input.response_builder
            .set_should_end_session(False)
            .speak(text)
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
        text = "Hasta luego"
        return (
            handler_input.response_builder
            .set_should_end_session(True) # al cancelar o parar, cerramos skill
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
            .set_should_end_session(True) # si hay un error cerramos
            .speak(speech)
            .response
        )


class SessionEndedRequestHandler(BaseHandler):
    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        # Any cleanup logic goes here.
        return (
            handler_input.response_builder
            .set_should_end_session(True)
            .speak("Cerrando")
            .response
        )


class IntentReflectorHandler(AbstractRequestHandler):
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input: HandlerInput, *args, **kwargs) -> Response:
        intent_name = ask_utils.get_intent_name(handler_input)
        text = f"Se ha activado el intent {intent_name}."
        return (
            handler_input.response_builder
            .set_should_end_session(True)
            .speak(text)
            .set_card(SimpleCard("Error", text))
            .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input: HandlerInput, exception) -> bool:
        return True

    def handle(self, handler_input: HandlerInput, exception, *args, **kwargs) -> Response:
        logging.error(exception, exc_info=True)

        text = "No pude hacer lo que has pedido, prueba de nuevo."

        return (
            handler_input.response_builder
            .set_should_end_session(True)
            .speak(text)
            .set_card(SimpleCard("Error", text))
            .response
        )


# ==========================================================
#      SKILL ADAPTER
# ==========================================================

skill_builder = SkillBuilder()

skill_builder.add_request_handler(SignUpIntentHandler())
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

skill_builder.add_request_handler(IntentReflectorHandler())  # último para que no sobre-escriba
skill_builder.add_exception_handler(CatchAllExceptionHandler())

skill_adapter = SkillAdapter(
    skill=skill_builder.create(),
    skill_id=info.skill_id,
    app=app
)


# ==========================================================
#      FLASK
# ==========================================================

@app.get("/")  # hello world al hacer GET
def hello_world():
    return "Hello world!"


@app.post("/")  # atiende peticiones POST
def invoke_skill():
    return skill_adapter.dispatch_request()


if __name__ == "__main__":
    pass
