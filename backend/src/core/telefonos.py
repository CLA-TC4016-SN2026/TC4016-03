"""Normalización de números a E.164 (RF-23)."""

import re

_SEPARADORES = re.compile(r"[\s\-().]")
_E164 = re.compile(r"^\+[1-9]\d{6,14}$")
# Prefijos mexicanos que se quitan, con la longitud total que dejan 10 dígitos.
_PREFIJOS_MX = (("521", 13), ("52", 12), ("044", 13), ("045", 13), ("01", 12))


def normalizar(texto: str) -> str | None:
    """E.164 del número, o None si no es un número telefónico.

    Mexicanos: +52 y 10 dígitos. Otros países: se conservan con su `+`.
    """
    limpio = _SEPARADORES.sub("", texto.strip())
    if limpio.startswith("+"):
        digitos = limpio[1:]
        if not digitos.isdigit():
            return None
        if digitos.startswith("521") and len(digitos) == 13:
            digitos = "52" + digitos[3:]
        candidato = "+" + digitos
        return candidato if _E164.match(candidato) else None
    if not limpio.isdigit():
        return None
    for prefijo, largo in _PREFIJOS_MX:
        if limpio.startswith(prefijo) and len(limpio) == largo:
            limpio = limpio[len(prefijo) :]
            break
    return "+52" + limpio if len(limpio) == 10 else None


def mostrado(e164: str) -> str:
    """Los números mexicanos se muestran a 10 dígitos (RF-23)."""
    return e164[3:] if e164.startswith("+52") and len(e164) == 13 else e164
