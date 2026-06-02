"""Cálculos de KPIs reutilizados nas várias visões.

Toda função recebe DataFrames já filtrados (mes_ref / empresa / obra) e
devolve dicionário com nomes em português."""
from __future__ import annotations

import pandas as pd

INATIVAS = {"Doente", "Licenciado", "Em"}


def kpi_basico(df_folha: pd.DataFrame) -> dict[str, float]:
    """Métricas-resumo da folha_mensal."""
    if df_folha.empty:
        return {
            "headcount": 0, "ativos": 0, "inativos": 0,
            "pct_inativos": 0.0,
            "proventos_total": 0.0, "liquido_total": 0.0,
            "salario_medio": 0.0,
        }
    head = len(df_folha)
    ativos = int((df_folha["situacao"] == "Ativo").sum())
    inativos = int(df_folha["situacao"].isin(list(INATIVAS)).sum())
    return {
        "headcount": head,
        "ativos": ativos,
        "inativos": inativos,
        "pct_inativos": inativos / head if head else 0.0,
        "proventos_total": float(pd.to_numeric(df_folha["proventos_total"], errors="coerce").sum()),
        "liquido_total":   float(pd.to_numeric(df_folha["liquido"], errors="coerce").sum()),
        "salario_medio":   float(pd.to_numeric(df_folha["salario_base"], errors="coerce").mean() or 0),
    }


def custo_estimado_com_encargos(proventos: float,
                                pct_encargos: float = 0.33) -> float:
    """proventos × (1 + encargos)."""
    return proventos * (1 + pct_encargos)


def turnover_mensal(admissoes: int, demissoes: int, headcount_medio: float) -> float:
    if not headcount_medio:
        return 0.0
    return (admissoes + demissoes) / 2 / headcount_medio


def comparativo_mensal(df_curr: pd.DataFrame, df_prev: pd.DataFrame) -> pd.DataFrame:
    """Identifica admissões e demissões entre dois meses."""
    if df_curr.empty:
        return pd.DataFrame()
    key = ["cod_empresa", "matricula"]
    cur_keys = set(map(tuple, df_curr[key].astype(str).values.tolist()))
    prev_keys = set(map(tuple, df_prev[key].astype(str).values.tolist())) if not df_prev.empty else set()

    novos = cur_keys - prev_keys
    saidos = prev_keys - cur_keys

    rows = []
    for emp, mat in novos:
        r = df_curr[(df_curr["cod_empresa"] == emp) & (df_curr["matricula"] == mat)].iloc[0]
        rows.append({"movimento": "ADMISSÃO", "cod_empresa": emp, "matricula": mat,
                     "nome": r.get("nome"), "cod_cargo": r.get("cod_cargo"),
                     "salario_base": r.get("salario_base"),
                     "data_evento": r.get("dt_admissao")})
    for emp, mat in saidos:
        r = df_prev[(df_prev["cod_empresa"] == emp) & (df_prev["matricula"] == mat)].iloc[0]
        rows.append({"movimento": "DEMISSÃO", "cod_empresa": emp, "matricula": mat,
                     "nome": r.get("nome"), "cod_cargo": r.get("cod_cargo"),
                     "salario_base": r.get("salario_base"),
                     "data_evento": r.get("dt_demissao")})
    return pd.DataFrame(rows)


def piramide_por_nivel(df_folha: pd.DataFrame,
                       cargos: pd.DataFrame) -> pd.DataFrame:
    """Conta funcionários por nível hierárquico (Aprendiz → Diretoria)."""
    if df_folha.empty:
        return pd.DataFrame()
    df = df_folha.merge(cargos[["cod_cargo", "nivel"]], on="cod_cargo", how="left")
    contagem = df.groupby("nivel", dropna=False).size().reset_index(name="quantidade")
    ordem = ["Aprendiz", "Servente", "Meio Oficial", "Oficial", "Especializado",
             "Apoio", "Encarregado", "Contramestre", "Admin", "Diretoria"]
    contagem["__ord"] = contagem["nivel"].apply(lambda x: ordem.index(x) if x in ordem else 99)
    return contagem.sort_values("__ord").drop(columns="__ord")


def ratio_oficial_servente(df_folha: pd.DataFrame,
                            cargos: pd.DataFrame) -> float:
    df = df_folha.merge(cargos[["cod_cargo", "nivel"]], on="cod_cargo", how="left")
    of = int((df["nivel"] == "Oficial").sum())
    se = int((df["nivel"] == "Servente").sum())
    return of / se if se else 0.0


def mask_cpf(cpf: str | None, mostrar_completo: bool = False) -> str:
    if not cpf:
        return ""
    if mostrar_completo:
        return cpf
    return f"{cpf[:3]}.***.***-{cpf[-2:]}"
