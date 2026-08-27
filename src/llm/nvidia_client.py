"""Cliente HTTP y parser estructurado para NVIDIA NIM (build.nvidia.com).

Permite conectar con modelos LLM en la nube (ej. meta/llama-3.2-90b-vision-instruct,
meta/llama-3.2-11b-vision-instruct) para la capa 2 de NLU zootécnico.
Utiliza únicamente la librería estándar (urllib.request + json) sin dependencias pesadas.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import date
from typing import Optional, Union

from ..parsers.event_parser import ParsedEvent
from ..parsers import nlp_engine as nlu
from ..utils import a_float, iso, normalizar, parse_fecha, to_date

logger = logging.getLogger("bitacora.llm")

DEFAULT_MODEL = "meta/llama-3.2-90b-vision-instruct"
DEFAULT_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

SYSTEM_PROMPT = """Eres el motor NLU zootécnico para una bitácora de campo ganadero.
Tu tarea es extraer eventos estructurados en JSON a partir de notas de voz o texto enviadas por mayordomos y personal de campo en español.

Los 8 eventos zootécnicos posibles son:
1. 'parto':
   - animal_tag: tag/arete de la vaca madre (ej: '47', 'n069')
   - datos:
     - sexo_cria: 'Macho' o 'Hembra' (o null)
     - estado_cria: 'VIVO' o 'MUERTO' (por defecto 'VIVO', 'MUERTO' si fue aborto o nació muerto)
     - peso_nacimiento: float en kg (o null)
     - id_cria: tag de la cría si se menciona (o null)

2. 'muerte':
   - animal_tag: tag del animal fallecido
   - datos:
     - causa_presunta: string con la causa sospechada (o null)

3. 'servicio':
   - animal_tag: tag de la vaca
   - datos:
     - tipo_servicio: 'IA' (inseminación artificial / pajilla) o 'MONTA' (monta directa/toro)
     - toro_pajilla: código o nombre del toro/pajuela (o null)
     - raza_toro: raza del toro si se indica (o null)

4. 'celo':
   - animal_tag: tag de la vaca
   - datos:
     - am_pm: 'AM' (mañana/madrugada) o 'PM' (tarde/noche) (o null)

5. 'tratamiento':
   - animal_tag: tag del animal
   - datos:
     - producto: nombre del medicamento/vacuna (o null)
     - dosis: dosis con unidad (ej: '20ml', '10 cc') (o null)
     - via: 'SC', 'IM', 'IV', 'Oral' (o null)
     - dias_retiro: int días totales de retiro (o null)
     - dias_retiro_leche: int si aplica a leche (o null)
     - dias_retiro_carne: int si aplica a carne (o null)

6. 'pesaje':
   - animal_tag: tag del animal
   - datos:
     - peso_kg: float (o null)
     - evento: 'Control', 'DESTETE', o 'NACIMIENTO' (por defecto 'Control')

7. 'traslado':
   - animal_tag: tag del animal o null si es por lote
   - datos:
     - lote: identificador del lote si aplica (o null)
     - potrero_origen: nombre/número del potrero de salida (o null)
     - potrero_destino: nombre/número del potrero de llegada (o null)

8. 'movimiento':
   - animal_tag: tag si aplica (o null)
   - datos:
     - tipo_movimiento: 'COMPRA', 'VENTA', 'SALIDA', o 'ENTRADA'
     - cantidad: int de animales si es grupo (o null)
     - procedencia_destino: origen o destino (o null)

Además, clasifica como 'consulta' si es una pregunta del usuario, o 'desconocido' si no se puede interpretar.

REGLAS DE RESPUESTA:
- Si la nota contiene MÚLTIPLES eventos (ej: 'pario la 47 ternero macho y vacune la 12 con oxitetraciclina 20ml'), extrae TODOS los eventos en la lista 'eventos'.
- Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta:
{
  "eventos": [
    {
      "tipo": "parto",
      "animal_tag": "47",
      "fecha": null,
      "datos": { ... }
    }
  ]
}
"""


def _extract_balanced_json(text: str) -> Optional[Union[dict, list]]:
    """Busca el primer bloque JSON balanceado ({...} o [...]) en el texto."""
    for start_char in ("[", "{"):
        start = text.find(start_char)
        while start != -1:
            # balance counting ignoring strings
            depth = 0
            in_str = False
            esc = False
            end = -1
            open_c = start_char
            close_c = "}" if start_char == "{" else "]"
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == open_c:
                        depth += 1
                    elif ch == close_c:
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                    elif start_char == "{" and ch == "[":
                        # anidamiento cruzado: contar brackets también de forma simplificada
                        pass
                    elif start_char == "[" and ch == "{":
                        pass
            if end != -1:
                candidate = text[start:end + 1]
                try:
                    parsed = json.loads(candidate)
                    # validar que sea JSON zootécnico relevante
                    if isinstance(parsed, dict) and ("tipo" in parsed or "eventos" in parsed or "events" in parsed):
                        return parsed
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                        return parsed
                    # si es JSON válido pero no zootécnico, igual intentar si no hay mejor opción
                    # seguir buscando uno más grande que contenga 'eventos'
                except json.JSONDecodeError:
                    pass
            start = text.find(start_char, start + 1)
    return None


def extract_json_from_text(raw_text: str) -> Optional[Union[dict, list]]:
    """Extrae y decodifica un objeto o array JSON embebido en una cadena."""
    if not raw_text:
        return None
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Intentar extracción balanceada (prioridad array si está a nivel raíz)
    balanced = _extract_balanced_json(text)
    if balanced is not None:
        return balanced

    # Fallback regex greedy para casos simples
    for pat in (r"(\[.*\])", r"(\{.*\})"):
        m = re.search(pat, text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    return None


class NvidiaClient:
    """Cliente para NVIDIA NIM API en integrate.api.nvidia.com."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        raw_key = api_key or os.getenv("NVIDIA_API_KEY", "")
        # Deshabilitado si es placeholder o vacía
        if raw_key in ("pegar_aqui_tu_clave_de_nvidia", "") or not raw_key.strip():
            self.api_key: Optional[str] = None
        else:
            self.api_key = raw_key.strip()

        self.model = model or os.getenv("NVIDIA_MODEL") or DEFAULT_MODEL
        self.api_url = base_url or os.getenv("NVIDIA_BASE_URL") or DEFAULT_API_URL
        self.timeout = timeout

    def is_available(self) -> bool:
        """Indica si el cliente cuenta con una API key configurada."""
        return bool(self.api_key and len(self.api_key) > 5)

    def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Envía una solicitud de chat completions al endpoint de NVIDIA NIM."""
        if not self.is_available():
            return None

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": max_tokens,
        }

        req = urllib.request.Request(
            url=self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "BitacoraCampo-NIM/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                return None
        except urllib.error.HTTPError as he:
            logger.warning("Error HTTP en NVIDIA NIM (%s): %s", he.code, he.reason)
            return None
        except urllib.error.URLError as ue:
            logger.warning("Error de red al conectar con NVIDIA NIM: %s", ue.reason)
            return None
        except TimeoutError:
            logger.warning("Timeout al conectar con NVIDIA NIM (>%ss)", self.timeout)
            return None
        except Exception as e:
            logger.warning("Excepción inesperada en NVIDIA NIM: %s", e)
            return None

    def parse_text(self, texto: str, hoy: Optional[date] = None) -> Optional[list[ParsedEvent]]:
        """Envía el texto al LLM y parsea la respuesta en una lista de ParsedEvent."""
        if not self.is_available() or not texto or not texto.strip():
            return None

        fecha_base = hoy or date.today()
        user_prompt = f"Nota de campo: «{texto}»\nFecha actual de referencia: {iso(fecha_base)}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_resp = self.chat_completion(messages)
        if not raw_resp:
            return None

        parsed_json = extract_json_from_text(raw_resp)
        if not parsed_json:
            logger.warning("No se pudo extraer JSON de la respuesta LLM: %s", raw_resp[:100])
            return None

        raw_events: list[dict] = []
        if isinstance(parsed_json, dict):
            if "eventos" in parsed_json and isinstance(parsed_json["eventos"], list):
                raw_events = parsed_json["eventos"]
            elif "events" in parsed_json and isinstance(parsed_json["events"], list):
                raw_events = parsed_json["events"]
            elif "tipo" in parsed_json:
                raw_events = [parsed_json]
        elif isinstance(parsed_json, list):
            raw_events = [it for it in parsed_json if isinstance(it, dict)]

        if not raw_events:
            return None

        eventos_resultado: list[ParsedEvent] = []
        for item in raw_events:
            tipo_raw = str(item.get("tipo", "desconocido")).strip().lower()
            tipo = self._normalizar_tipo(tipo_raw)

            # Animal tag
            tag_raw = item.get("animal_tag")
            tag = self._normalizar_tag(tag_raw)

            # Fecha
            fecha_raw = item.get("fecha")
            if fecha_raw:
                f_obj = parse_fecha(str(fecha_raw), fecha_base) or to_date(fecha_raw)
                fecha = iso(f_obj or fecha_base)
            else:
                fecha = iso(parse_fecha(texto, fecha_base) or fecha_base)

            # Datos
            datos_raw = item.get("datos", {})
            datos = dict(datos_raw) if isinstance(datos_raw, dict) else {}
            datos = self._limpiar_datos(tipo, datos, texto)

            eventos_resultado.append(
                ParsedEvent(
                    tipo=tipo,
                    texto=texto,
                    animal_tag=tag,
                    fecha=fecha,
                    datos=datos,
                )
            )

        return eventos_resultado if eventos_resultado else None

    def _normalizar_tipo(self, tipo_raw: str) -> str:
        """Normaliza el tipo de evento a uno de los 8 oficiales o consulta/desconocido."""
        if tipo_raw in ("inseminacion", "inseminación", "ia", "monta", "servicio"):
            return "servicio"
        if tipo_raw in ("parto", "alumbramiento", "nacimiento"):
            return "parto"
        if tipo_raw in ("muerte", "baja_muerte", "fallecimiento"):
            return "muerte"
        if tipo_raw in ("celo", "calor", "caleando"):
            return "celo"
        if tipo_raw in ("tratamiento", "medicacion", "medicación", "vacunacion", "vacunación", "desparasitacion", "desparasitación"):
            return "tratamiento"
        if tipo_raw in ("pesaje", "peso"):
            return "pesaje"
        if tipo_raw in ("traslado", "rotacion", "rotación", "cambio_potrero"):
            return "traslado"
        if tipo_raw in ("movimiento", "compra", "venta", "entrada", "salida"):
            return "movimiento"
        if tipo_raw in ("consulta", "pregunta", "historial"):
            return "consulta"
        if tipo_raw in ("parto", "muerte", "servicio", "celo", "tratamiento", "pesaje", "traslado", "movimiento", "consulta", "desconocido"):
            return tipo_raw
        return "desconocido"

    def _normalizar_tag(self, tag_raw: Optional[str]) -> Optional[str]:
        """Normaliza tags de animales."""
        if not tag_raw:
            return None
        t = str(tag_raw).strip()
        if t.lower() in ("null", "none", "", "no aplica", "n/a"):
            return None
        t = re.sub(r"^(?:la|el|vaca|animal|arete|tag|nro|numero)\s+", "", t, flags=re.IGNORECASE).strip()
        t = normalizar(t)
        return t or None

    def _limpiar_datos(self, tipo: str, datos: dict, texto_completo: str) -> dict:
        """Limpia y convalida los datos extraídos según las reglas de negocio."""
        if tipo == "parto":
            sexo = datos.get("sexo_cria")
            if sexo:
                s_str = str(sexo).strip().capitalize()
                if s_str.startswith("M") or s_str == "Macho":
                    datos["sexo_cria"] = "Macho"
                elif s_str.startswith("H") or s_str == "Hembra":
                    datos["sexo_cria"] = "Hembra"
            estado = datos.get("estado_cria")
            if estado and "muert" in str(estado).lower():
                datos["estado_cria"] = "MUERTO"
            else:
                datos["estado_cria"] = "VIVO"
            if "peso_nacimiento" in datos:
                datos["peso_nacimiento"] = a_float(datos["peso_nacimiento"])
            if "id_cria" in datos and datos["id_cria"]:
                datos["id_cria"] = self._normalizar_tag(str(datos["id_cria"]))

        elif tipo == "servicio":
            t_serv = str(datos.get("tipo_servicio", "IA")).upper()
            datos["tipo_servicio"] = "MONTA" if "MONT" in t_serv else "IA"

        elif tipo == "celo":
            am_pm = datos.get("am_pm")
            if am_pm:
                am_pm_str = str(am_pm).upper()
                datos["am_pm"] = "AM" if "AM" in am_pm_str else ("PM" if "PM" in am_pm_str else None)

        elif tipo == "tratamiento":
            if "dias_retiro" in datos and datos["dias_retiro"] is not None:
                try:
                    datos["dias_retiro"] = int(datos["dias_retiro"])
                except (ValueError, TypeError):
                    pass
            dias = datos.get("dias_retiro")
            if dias:
                retiro = nlu.retiro_leche_carne(texto_completo, dias)
                if datos.get("dias_retiro_leche") is None:
                    datos["dias_retiro_leche"] = retiro["dias_retiro_leche"]
                if datos.get("dias_retiro_carne") is None:
                    datos["dias_retiro_carne"] = retiro["dias_retiro_carne"]

        elif tipo == "pesaje":
            if "peso_kg" in datos:
                datos["peso_kg"] = a_float(datos["peso_kg"])
            if not datos.get("evento"):
                datos["evento"] = "Control"

        elif tipo == "movimiento":
            if "cantidad" in datos and datos["cantidad"] is not None:
                try:
                    datos["cantidad"] = int(datos["cantidad"])
                except (ValueError, TypeError):
                    pass

        return datos


def try_llm_parse(
    texto: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    hoy: Optional[date] = None,
    timeout: float = 30.0,
) -> Optional[Union[ParsedEvent, list[ParsedEvent]]]:
    """Intenta parsear un texto usando el LLM de NVIDIA NIM si está configurado.

    Devuelve:
    - ParsedEvent si se detectó exactamente 1 evento.
    - list[ParsedEvent] si se detectaron múltiples eventos.
    - None si el LLM no está disponible, falló la conexión o no pudo interpretar.
    """
    client = NvidiaClient(api_key=api_key, model=model, timeout=timeout)
    if not client.is_available():
        return None

    eventos = client.parse_text(texto, hoy=hoy)
    if not eventos:
        return None

    if len(eventos) == 1:
        return eventos[0]
    return eventos
