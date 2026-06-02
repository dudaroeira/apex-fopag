"""Padronizacao de campos extraidos do analitico."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional

MES_PT = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "ABRIL": 4,
    "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9,
    "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
}

SITUACOES_VALIDAS = {
    "ATIVO": "Ativo",
    "DOENTE": "Doente",
    "LICENCIADO": "Licenciado",
    "EM": "Em",
    "AFASTADO": "Em",
    "AFASTAMENTO": "Em",
    "DEMITIDO": "Demitido",
}

KNOWN_OBRA_CODES = (
    "204OB",
    "JAX28",
    "OBRA99",
    "REPARO",
    "1AD",
)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_mes_ref(header_text):
    m = re.search(r"FOLHA ANAL[ÍI]TICA\s*-\s*([A-ZÇÃÕÉÍ]+)\s*/\s*(\d{4})", header_text.upper())
    if not m:
        return None
    mes_nome = strip_accents(m.group(1).upper())
    ano = int(m.group(2))
    mes = MES_PT.get(mes_nome)
    if not mes:
        return None
    return f"{ano:04d}-{mes:02d}"


def parse_decimal(s):
    if s is None or s == "":
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace("R$", "").replace(" ", "")
    if "," in s and "." in s and s.rfind(".") < s.rfind(","):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_data(s):
    if not s:
        return None
    s = str(s).strip()
    if not s or s in {"//", "00/00/0000"}:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normaliza_situacao(s):
    if not s:
        return "Ativo"
    key = strip_accents(str(s)).upper().strip()
    return SITUACOES_VALIDAS.get(key, key.title())


def normaliza_cpf(s):
    if not s:
        return None
    digits = re.sub(r"\D", "", str(s))
    if len(digits) < 11:
        digits = digits.zfill(11)
    return digits[-11:] if digits else None


def normaliza_pis(s):
    if not s:
        return None
    digits = re.sub(r"\D", "", str(s))
    return digits or None


def clean_text(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def normalize_cod_obra(raw, fallback_len=5):
    if not raw:
        return None
    s = clean_text(raw).upper()
    if not s:
        return None
    if s in KNOWN_OBRA_CODES:
        return s
    for code in sorted(KNOWN_OBRA_CODES, key=len, reverse=True):
        if s.startswith(code):
            return code
    return s[:fallback_len]
