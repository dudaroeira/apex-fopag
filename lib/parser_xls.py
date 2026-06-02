"""Parser do XLS Folha Analitica do escritorio.

Layout observado (saida padrao do sistema):

  Header global:
    r4: Empresa: | _ | _ | cod_empresa | razao | _ ... | CNPJ: | cnpj
    r5: Obra:    | _ | _ | cod_obra    | nome  | _ ... | CNPJ/CNO: | cnpj_cno

  Bloco por funcionario:
    Funcionario: | _ | _ | matricula | _ | _ | nome | ... | 'Situacao: X NOME'
    Nascimento:  | _ | _ | dt        | _ | _ | CPF: | _ | cpf | _ | _ | PIS: | _ | _ | _ | Dep IR: | n
    Dt. admissao:| _ | _ | dt        | _ | _ | Dt. demissao: | _ | _ | dt | _ | _ | _ | _ | _ | Departamento: | 'cod nome'
    Salario:     | _ | _ | val       | cod_cargo | _ | Cargo: | _ | nome_cargo | cod_funcao | _ | _ | _ | _ | _ | Funcao: | nome_funcao
    P R O V E N T O S | _ ... | D E S C O N T O S
    Cod | Descricao | _ | _ | _ | _ | _ | Qtde | _ | _ | Valor  (col 11)
    Cod | Descricao | _ | _ | _ | _ | _ | Qtde | _ | _ | Valor  (col 22)
    Proventos: | _ | _ | total | _ | _ | Descontos: | _ | _ | _ | total
    LIQUIDO:    | _ | _ | _ | _ | valor
    Base INSS:  | _ | _ | val | Base INSS fer: | ... | Base FGTS: | _ | val | FGTS: | _ | val | ...
    Base IRRF:  ...
"""
from __future__ import annotations

import re
from typing import Any, Optional

import xlrd

from .normalizar import (
    clean_text,
    normalize_cod_obra,
    normaliza_cpf,
    normaliza_pis,
    normaliza_situacao,
    parse_data,
    parse_decimal,
    parse_mes_ref,
)


def _cell(sheet, r, c):
    if r < 0 or r >= sheet.nrows or c < 0 or c >= sheet.ncols:
        return ""
    v = sheet.cell_value(r, c)
    if v in ("", None):
        return ""
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    return str(v).strip()


def _row(sheet, r):
    return [_cell(sheet, r, c) for c in range(sheet.ncols)]


def _row_text(sheet, r):
    return " ".join(x for x in _row(sheet, r) if x)


def _next_nonempty(row, start_col):
    for c in range(start_col + 1, len(row)):
        if row[c]:
            return c, row[c]
    return -1, ""


def _value_after(row, label):
    for c, v in enumerate(row):
        if v and label in v:
            _, val = _next_nonempty(row, c)
            return val
    return ""


def _idx_of(row, exact_value):
    for c, v in enumerate(row):
        if v == exact_value:
            return c
    return -1


def _idx_contains(row, substring):
    for c, v in enumerate(row):
        if v and substring in v:
            return c
    return -1


def _values_after_label_run(row):
    """Para linhas com varios labels (Nascimento + CPF + PIS),
    associa cada label ao primeiro valor nao-vazio depois dele."""
    out = {}
    for idx, val in enumerate(row):
        if val and val.endswith(":") and len(val) > 1:
            label = val[:-1].strip()
            for j in range(idx + 1, len(row)):
                if row[j] and not row[j].endswith(":"):
                    out[label] = row[j]
                    break
    return out


def _is_int_like(s):
    if not s:
        return False
    s = str(s).strip()
    if not s:
        return False
    return s.replace(".", "").replace("-", "").isdigit()


# ---------------------------------------------------------------------------

def parse_xls(path):
    wb = xlrd.open_workbook(path, ignore_workbook_corruption=True)
    sheet = wb.sheet_by_index(0)

    mes_ref = None
    empresa = {}
    obra = {}
    func_start_rows = []

    for r in range(sheet.nrows):
        text = _row_text(sheet, r)
        if mes_ref is None:
            mes_ref = parse_mes_ref(text)
        row = _row(sheet, r)

        if "Empresa:" in row:
            idx = _idx_of(row, "Empresa:")
            cod_idx, cod = _next_nonempty(row, idx)
            _, razao = _next_nonempty(row, cod_idx) if cod_idx >= 0 else (-1, "")
            cnpj = _value_after(row, "CNPJ:")
            empresa = {
                "cod_empresa": cod,
                "razao_social": clean_text(razao),
                "cnpj": clean_text(cnpj),
            }
        elif "Obra:" in row:
            idx = _idx_of(row, "Obra:")
            cod_idx, cod = _next_nonempty(row, idx)
            _, nome = _next_nonempty(row, cod_idx) if cod_idx >= 0 else (-1, "")
            cnpj_cno = _value_after(row, "CNPJ/CNO:")
            obra = {
                "cod_obra": normalize_cod_obra(cod) or cod,
                "nome_obra": clean_text(nome),
                "cnpj_cno": clean_text(cnpj_cno),
            }
        elif "Funcionário:" in row or "Funcionario:" in row:
            func_start_rows.append(r)

    funcionarios = []
    for i, r0 in enumerate(func_start_rows):
        r_end = func_start_rows[i + 1] if i + 1 < len(func_start_rows) else sheet.nrows
        f = _parse_bloco(sheet, r0, r_end)
        if f:
            funcionarios.append(f)

    return {
        "mes_ref": mes_ref,
        "empresa": empresa,
        "obra": obra,
        "funcionarios": funcionarios,
        "arquivo_origem": path,
    }


def _parse_bloco(sheet, r0, r_end):
    row0 = _row(sheet, r0)

    # Funcionario: | _ | _ | cod | _ | _ | nome
    idx_label = _idx_of(row0, "Funcionário:")
    if idx_label < 0:
        idx_label = _idx_of(row0, "Funcionario:")
    if idx_label < 0:
        return None
    cod_idx, matricula = _next_nonempty(row0, idx_label)
    _, nome = _next_nonempty(row0, cod_idx) if cod_idx >= 0 else (-1, "")
    if not matricula or not nome:
        return None

    # Situacao: dentro de uma celula tipo "Situacao: 0  Ativo"
    sit = ""
    for v in row0:
        if v and ("Situação:" in v or "Situacao:" in v):
            m = re.search(r"Situa[cç][aã]o:\s*\d+\s*(\w+)", v)
            if m:
                sit = m.group(1)
            break

    func = {
        "matricula": matricula,
        "nome": clean_text(nome),
        "situacao": normaliza_situacao(sit),
        "cpf": None, "pis": None, "nascimento": None,
        "dt_admissao": None, "dt_demissao": None,
        "cod_departamento": None, "nome_departamento": "",
        "cod_cargo": None, "nome_cargo": "",
        "cod_funcao": None, "nome_funcao": "",
        "salario_base": 0.0,
        "proventos_total": 0.0, "descontos_total": 0.0,
        "liquido": 0.0,
        "base_inss": 0.0, "base_fgts": 0.0, "fgts": 0.0, "base_irrf": 0.0,
        "dependentes_ir": 0,
        "eventos": [],
    }

    eventos_started = False
    for r in range(r0 + 1, r_end):
        row = _row(sheet, r)
        text = _row_text(sheet, r)

        if "Nascimento:" in text:
            kv = _values_after_label_run(row)
            func["nascimento"] = parse_data(kv.get("Nascimento"))
            func["cpf"] = normaliza_cpf(kv.get("CPF"))
            func["pis"] = normaliza_pis(kv.get("PIS"))
            dep_ir = kv.get("Dependente IR") or "0"
            try:
                func["dependentes_ir"] = int(parse_decimal(dep_ir))
            except Exception:
                func["dependentes_ir"] = 0
        elif "Dt. admissão:" in text or "Dt. admissao:" in text:
            # Layout: c0='Dt. admissão:' c3=dt | c6='Dt. demissão:' c9=cod_dep
            #         c14='Departamento:' c16=nome_dep
            # IMPORTANTE: c9 NAO eh dt_demissao -- eh cod_departamento.
            # dt_demissao raramente vem preenchido nesse layout.
            adm_idx = _idx_of(row, "Dt. admissão:")
            if adm_idx < 0:
                adm_idx = _idx_of(row, "Dt. admissao:")
            if adm_idx >= 0:
                _, dt_adm = _next_nonempty(row, adm_idx)
                func["dt_admissao"] = parse_data(dt_adm)

            dem_idx = _idx_of(row, "Dt. demissão:")
            if dem_idx < 0:
                dem_idx = _idx_of(row, "Dt. demissao:")
            dep_idx = _idx_of(row, "Departamento:")

            if dep_idx > 0:
                # nome_dep = primeira cell nao-vazia depois de "Departamento:"
                _, nome_dep = _next_nonempty(row, dep_idx)
                func["nome_departamento"] = clean_text(nome_dep)
                # cod_dep = ultima cell numerica entre Dt. demissao: e Departamento:
                lower = dem_idx if dem_idx > 0 else adm_idx
                for c in range(dep_idx - 1, lower, -1):
                    val = row[c]
                    if val and _is_int_like(val):
                        func["cod_departamento"] = val
                        break
                # dt_demissao: se houver algo entre Dt. demissao: e cod_dep que pareca data
                if dem_idx > 0 and func["cod_departamento"]:
                    cod_idx = _idx_of(row, func["cod_departamento"])
                    for c in range(dem_idx + 1, cod_idx):
                        val = row[c]
                        if val and "/" in val:
                            func["dt_demissao"] = parse_data(val)
                            break
            else:
                # JR6: sem Departamento, dt_demissao pode estar direto apos Dt. demissao:
                if dem_idx > 0:
                    _, dt_dem = _next_nonempty(row, dem_idx)
                    if dt_dem and "/" in dt_dem:
                        func["dt_demissao"] = parse_data(dt_dem)
        elif "Salário:" in row and "Cargo:" in row:
            sal_idx = _idx_of(row, "Salário:")
            _, sal_val = _next_nonempty(row, sal_idx)
            func["salario_base"] = parse_decimal(sal_val)

            cargo_idx = _idx_of(row, "Cargo:")
            funcao_idx = _idx_of(row, "Função:")

            if cargo_idx > 0:
                # nome_cargo = primeira celula nao-vazia depois de "Cargo:"
                next_idx, nome_cargo = _next_nonempty(row, cargo_idx)
                func["nome_cargo"] = clean_text(nome_cargo)
                # cod_cargo = ultima celula numerica entre sal_idx e cargo_idx
                # (geralmente ali esta 'cod_cargo' antes do label "Cargo:")
                for c in range(cargo_idx - 1, sal_idx, -1):
                    val = row[c]
                    if val and _is_int_like(val) and val != sal_val:
                        func["cod_cargo"] = val
                        break
                # cod_funcao = celula numerica logo depois de nome_cargo
                if funcao_idx > cargo_idx:
                    for c in range(next_idx + 1, funcao_idx):
                        val = row[c]
                        if val and _is_int_like(val):
                            func["cod_funcao"] = val
                            break

            if funcao_idx > 0:
                _, nome_funcao = _next_nonempty(row, funcao_idx)
                func["nome_funcao"] = clean_text(nome_funcao)

        elif "Proventos:" in text and "Descontos:" in text:
            func["proventos_total"] = parse_decimal(_value_after(row, "Proventos:"))
            func["descontos_total"] = parse_decimal(_value_after(row, "Descontos:"))
        elif "LÍQUIDO:" in text or "LIQUIDO:" in text:
            liq_idx = _idx_contains(row, "LÍQUIDO")
            if liq_idx < 0:
                liq_idx = _idx_contains(row, "LIQUIDO")
            if liq_idx >= 0:
                _, liq_val = _next_nonempty(row, liq_idx)
                func["liquido"] = parse_decimal(liq_val)
        elif "Base INSS:" in row and "Base FGTS:" in row:
            kv = _values_after_label_run(row)
            func["base_inss"] = parse_decimal(kv.get("Base INSS", "0"))
            func["base_fgts"] = parse_decimal(kv.get("Base FGTS", "0"))
            func["fgts"] = parse_decimal(kv.get("FGTS", "0"))
        elif "Base IRRF:" in row:
            kv = _values_after_label_run(row)
            func["base_irrf"] = parse_decimal(kv.get("Base IRRF", "0"))
        elif "P R O V E N T O S" in text and "D E S C O N T O S" in text:
            eventos_started = True
        elif eventos_started:
            # Proventos: cols 2,3 (cod, desc), 8 (qtde), 11 (valor)
            # Descontos: cols 14,15 (cod, desc), 20 (qtde), 22 (valor)
            for inicio, val_col, tipo in [(2, 11, "PROVENTO"), (14, 22, "DESCONTO")]:
                cod = _cell(sheet, r, inicio)
                desc = _cell(sheet, r, inicio + 1)
                qtd = _cell(sheet, r, inicio + 6)
                val = _cell(sheet, r, val_col)
                if cod and desc and val and _is_int_like(cod):
                    func["eventos"].append({
                        "cod_rubrica": cod,
                        "descricao": clean_text(desc),
                        "quantidade": parse_decimal(qtd),
                        "valor": parse_decimal(val),
                        "tipo": tipo,
                    })

    return func
