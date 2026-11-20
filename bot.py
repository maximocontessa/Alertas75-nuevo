
import os
import json
import re
import unicodedata
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API_KEY = os.environ["FOOTBALL_API_KEY"]

TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"
API = "https://v3.football.api-sports.io"

STATE_FILE = "state.json"


def cargar_estado():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"offset": 0, "partidos": [], "avisados": []}


def guardar_estado():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def enviar(texto):
    requests.post(
        f"{TELEGRAM}/sendMessage",
        json={"chat_id": CHAT_ID, "text": texto},
        timeout=20
    ).raise_for_status()


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def procesar_comandos():
    respuesta = requests.get(
        f"{TELEGRAM}/getUpdates",
        params={"offset": estado["offset"] + 1, "timeout": 0},
        timeout=20
    )
    respuesta.raise_for_status()

    for update in respuesta.json().get("result", []):
        estado["offset"] = update["update_id"]

        mensaje = update.get("message", {})
        chat = mensaje.get("chat", {})
        texto = mensaje.get("text", "").strip()

        if str(chat.get("id")) != str(CHAT_ID):
            continue

        if texto == "/start":
            enviar("¡Bot de alertas de fútbol activado! ⚽\nEscribe /ayuda para ver los comandos.")

        elif texto == "/ayuda":
            enviar(
                "COMANDOS ⚽\n"
                "/anadir Equipo - Equipo\n"
                "/lista\n"
                "/borrar 1\n"
                "/ayuda"
            )

        elif texto.startswith("/anadir "):
            partido = texto.replace("/anadir ", "", 1).strip()
            if " - " not in partido:
                enviar("Escribe el partido así:\n/anadir Real Madrid - Barcelona")
            elif partido not in estado["partidos"]:
                estado["partidos"].append(partido)
                guardar_estado()
                enviar(f"Partido añadido: {partido} ⚽")
            else:
                enviar("Ese partido ya está en tu lista.")

        elif texto == "/lista":
            if not estado["partidos"]:
                enviar("Todavía no tienes partidos seleccionados.")
            else:
                lista = "\n".join(
                    f"{i + 1}. {p}" for i, p in enumerate(estado["partidos"])
                )
                enviar("Tus partidos:\n" + lista)

        elif texto.startswith("/borrar "):
            try:
                numero = int(texto.split()[1]) - 1
                partido = estado["partidos"].pop(numero)
                guardar_estado()
                enviar(f"Partido eliminado: {partido}")
            except (ValueError, IndexError):
                enviar("Número incorrecto. Consulta primero /lista.")


def consultar_partidos():
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")

    respuesta = requests.get(
        f"{API}/fixtures",
        headers={"x-apisports-key": API_KEY},
        params={"date": hoy, "timezone": "Europe/Madrid"},
        timeout=30
    )
    respuesta.raise_for_status()

    for partido in respuesta.json().get("response", []):
        fixture = partido["fixture"]
        equipos = partido["teams"]
        goles = partido["goals"]

        local = equipos["home"]["name"]
        visitante = equipos["away"]["name"]
        identificador = str(fixture["id"])

        estado_partido = fixture["status"]["short"]
        minuto = fixture["status"]["elapsed"] or 0

        if estado_partido not in ("2H", "FT") or minuto < 75:
            continue

        if identificador in estado["avisados"]:
            continue

        nombres = normalizar(local + " " + visitante)

        for seleccionado in estado["partidos"]:
            equipos_buscados = seleccionado.split(" - ")
            if len(equipos_buscados) != 2:
                continue

            primero = normalizar(equipos_buscados[0])
            segundo = normalizar(equipos_buscados[1])

            if primero in nombres and segundo in nombres:
                marcador = f"{goles['home']} - {goles['away']}"
                enviar(
                    f"⚽ ALERTA DE PARTIDO\n\n"
                    f"{local} {marcador} {visitante}\n"
                    f"Minuto detectado: {minuto}'"
                )
                estado["avisados"].append(identificador)
                guardar_estado()
                break


estado = cargar_estado()

try:
    procesar_comandos()
    consultar_partidos()
    guardar_estado()
except Exception as error:
    print(f"Error: {error}")
    raise
