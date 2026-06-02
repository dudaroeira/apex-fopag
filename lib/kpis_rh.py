"""KPIs de RH ricos — usados nas telas do app.

Convenções:
- Todas as funções recebem DataFrames já filtrados pelo mes_ref relevante.
- Retornos são floats ou DataFrames com nomes em português.
- Encargos: obra = 33% (INSS+RAT+FGTS+FAP+SECONCI+13/férias provisionado);
            admin = 30%.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd

INATIVOS = {"Doente", "Licenciado", "Em", "Demitido"}
ATIVOS = {"Ativo"}


def _hoje() -> date:
    return date.today()


def _to_date(x) -> Optional[date]:
    if pd.isna(x) or x is None or x == "":
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    try:
        return pd.to_datetime(x).date()
    except Exception:
        return None


def custo_com_encargos(
    df: pd.DataFrame,
    pct_obra: float = 0.33,
    pct_admin: float = 0.30,
) -> float:
    """Custo total de folha estimado, com encargos.

    Aplica pct_admin pra quem tem cod_departamento não vazio (e cod_obra=1AD ou similar),
    pct_obra pra todo o resto (canteiros). Para o caso onde não dá pra decidir,
    usa pct_obra (conservador).
    """
    if df.empty:
        return 0.0
    df = df.copy()
    df["proventos_total"] = pd.to_numeric(df["proventos_total"], errors="coerce").fillna(0)

    def encargo_row(row):
        cod_obra = str(row.get("cod_obra") or "")
        cod_dep = str(row.get("cod_departamento") or "")
        is_admin = cod_obra == "1AD" or "ADM" in (row.get("nome_departamento", "") or "").upper()
        return row["proventos_total"] * (1 + (pct_admin if is_admin else pct_obra))

    return float(df.apply(encargo_row, axis=1).sum())


def custo_medio(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    prov = pd.to_numeric(df["proventos_total"], errors="coerce").fillna(0).sum()
    return float(prov / len(df))


def pct_inativos(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(df["situacao"].isin(list(INATIVOS)).sum() / len(df))


def situacao_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["situacao", "quantidade", "pct"])
    s = df["situacao"].value_counts().reset_index()
    s.columns = ["situacao", "quantidade"]
    s["pct"] = s["quantidade"] / len(df)
    return s


def turnover_mensal(df_curr: pd.DataFrame, df_prev: pd.DataFrame) -> float:
    """(admissões + demissões) / 2 / headcount médio."""
    if df_curr.empty:
        return 0.0
    key_curr = set(zip(df_curr["cod_empresa"].astype(str), df_curr["matricula"].astype(str)))
    key_prev = set(zip(df_prev["cod_empresa"].astype(str), df_prev["matricula"].astype(str))) if not df_prev.empty else set()
    adm = len(key_curr - key_prev)
    dem = len(key_prev - key_curr)
    hc_medio = (len(df_curr) + len(df_prev)) / 2 if not df_prev.empty else len(df_curr)
    if hc_medio == 0:
        return 0.0
    return (adm + dem) / 2 / hc_medio


def movimentacoes(df_curr: pd.DataFrame, df_prev: pd.DataFrame) -> dict:
    if df_curr.empty:
        return {"admissoes": pd.DataFrame(), "demissoes": pd.DataFrame()}
    cur_keys = set(zip(df_curr["cod_empresa"].astype(str), df_curr["matricula"].astype(str)))
    prev_keys = set(zip(df_prev["cod_empresa"].astype(str), df_prev["matricula"].astype(str))) if not df_prev.empty else set()
    novos_keys = cur_keys - prev_keys
    saidos_keys = prev_keys - cur_keys
    df_curr["_k"] = list(zip(df_curr["cod_empresa"].astype(str), df_curr["matricula"].astype(str)))
    adm = df_curr[df_curr["_k"].isin(novos_keys)].drop(columns="_k")
    if not df_prev.empty:
        df_prev = df_prev.copy()
        df_prev["_k"] = list(zip(df_prev["cod_empresa"].astype(str), df_prev["matricula"].astype(str)))
        dem = df_prev[df_prev["_k"].isin(saidos_keys)].drop(columns="_k")
    else:
        dem = pd.DataFrame()
    return {"admissoes": adm, "demissoes": dem}


def tempo_de_casa_medio_anos(df: pd.DataFrame, ref: Optional[date] = None) -> float:
    if df.empty or "dt_admissao" not in df.columns:
        return 0.0
    ref = ref or _hoje()
    anos = []
    for x in df["dt_admissao"]:
        d = _to_date(x)
        if d:
            anos.append((ref - d).days / 365.25)
    return float(sum(anos) / len(anos)) if anos else 0.0


def faixas_tempo_casa(df: pd.DataFrame, ref: Optional[date] = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    ref = ref or _hoje()
    bins = []
    for x in df["dt_admissao"]:
        d = _to_date(x)
        if d is None:
            bins.append("Desconhecido")
            continue
        anos = (ref - d).days / 365.25
        if anos < 1:
            bins.append("≤ 1 ano")
        elif anos < 3:
            bins.append("1–3 anos")
        elif anos < 5:
            bins.append("3–5 anos")
        elif anos < 10:
            bins.append("5–10 anos")
        else:
            bins.append("10+ anos")
    s = pd.Series(bins).value_counts().reset_index()
    s.columns = ["Faixa", "Quantidade"]
    ordem = ["≤ 1 ano", "1–3 anos", "3–5 anos", "5–10 anos", "10+ anos", "Desconhecido"]
    s["_o"] = s["Faixa"].apply(lambda x: ordem.index(x) if x in ordem else 99)
    return s.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def faixas_etarias(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "nascimento" not in df.columns:
        return pd.DataFrame()
    hoje = _hoje()
    bins = []
    for x in df["nascimento"]:
        d = _to_date(x)
        if d is None:
            bins.append("Desconhecido")
            continue
        idade = (hoje - d).days // 365
        if idade <= 30:
            bins.append("≤ 30")
        elif idade <= 45:
            bins.append("31–45")
        elif idade <= 60:
            bins.append("46–60")
        else:
            bins.append("60+")
    s = pd.Series(bins).value_counts().reset_index()
    s.columns = ["Faixa", "Quantidade"]
    ordem = ["≤ 30", "31–45", "46–60", "60+", "Desconhecido"]
    s["_o"] = s["Faixa"].apply(lambda x: ordem.index(x) if x in ordem else 99)
    return s.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def top_cargos_por_custo(df: pd.DataFrame, cargos: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    base = df.merge(cargos[["cod_cargo", "nome_cargo"]], on="cod_cargo", how="left")
    base["proventos_total"] = pd.to_numeric(base["proventos_total"], errors="coerce").fillna(0)
    base["salario_base"] = pd.to_numeric(base["salario_base"], errors="coerce").fillna(0)
    g = (base.groupby("nome_cargo")
              .agg(quantidade=("matricula", "count"),
                   folha_bruta=("proventos_total", "sum"),
                   salario_medio=("salario_base", "mean"))
              .reset_index()
              .sort_values("folha_bruta", ascending=False)
              .head(n))
    g["nome_cargo"] = g["nome_cargo"].fillna("(sem cadastro)")
    return g.rename(columns={
        "nome_cargo": "Cargo",
        "quantidade": "Qtd.",
        "folha_bruta": "Folha bruta",
        "salario_medio": "Sal. médio",
    })


def piramide_hierarquica(df: pd.DataFrame, cargos: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    base = df.merge(cargos[["cod_cargo", "nivel"]], on="cod_cargo", how="left")
    s = base.groupby("nivel", dropna=False).size().reset_index(name="quantidade")
    ordem = ["Aprendiz", "Servente", "Meio Oficial", "Oficial", "Especializado",
             "Apoio", "Encarregado", "Contramestre", "Admin", "Diretoria"]
    s["nivel"] = s["nivel"].fillna("(sem nivel)")
    s["_o"] = s["nivel"].apply(lambda x: ordem.index(x) if x in ordem else 99)
    return s.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def ratio_oficial_servente(df: pd.DataFrame, cargos: pd.DataFrame) -> float:
    base = df.merge(cargos[["cod_cargo", "nivel"]], on="cod_cargo", how="left")
    of = int((base["nivel"] == "Oficial").sum())
    se = int((base["nivel"] == "Servente").sum())
    return of / se if se else 0.0


def pct_aprendizes(df: pd.DataFrame, cargos: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    base = df.merge(cargos[["cod_cargo", "demanda_aprendiz", "nivel"]],
                    on="cod_cargo", how="left")
    aprendizes = int((base["nivel"] == "Aprendiz").sum())
    base_lei = int(base["demanda_aprendiz"].fillna(False).sum())
    if not base_lei:
        base_lei = max(1, len(base))
    return aprendizes / base_lei


def alertas(df_curr: pd.DataFrame, df_prev: Optional[pd.DataFrame],
            cargos: pd.DataFrame, parametros: Optional[pd.DataFrame] = None) -> list[dict]:
    out = []
    if df_curr.empty:
        return out
    pct_inat_max = 0.15
    pct_turn_max = 0.05
    aprendiz_min = 0.05
    aprendiz_max = 0.15
    if parametros is not None and not parametros.empty:
        d = dict(zip(parametros["parametro"], parametros["valor"]))
        pct_inat_max = float(d.get("meta_inativos_max_pct", pct_inat_max))
        pct_turn_max = float(d.get("meta_turnover_max_pct", pct_turn_max))
        aprendiz_min = float(d.get("meta_aprendiz_min_pct", aprendiz_min))
        aprendiz_max = float(d.get("meta_aprendiz_max_pct", aprendiz_max))
    pct_inat = pct_inativos(df_curr)
    if pct_inat > pct_inat_max:
        out.append({
            "nivel": "vermelho",
            "titulo": "Inativos acima da meta",
            "msg": f"{pct_inat*100:.1f}% da folha está em afastamento/doença/licença (meta ≤ {pct_inat_max*100:.0f}%).",
        })
    if df_prev is not None and not df_prev.empty:
        turn = turnover_mensal(df_curr, df_prev)
        if turn > pct_turn_max:
            out.append({
                "nivel": "amarelo",
                "titulo": "Turnover acima da meta",
                "msg": f"Turnover do período em {turn*100:.1f}% (meta ≤ {pct_turn_max*100:.0f}%).",
            })
    apr = pct_aprendizes(df_curr, cargos)
    if apr < aprendiz_min:
        out.append({
            "nivel": "vermelho",
            "titulo": "Lei do Aprendiz — abaixo do piso",
            "msg": f"Apenas {apr*100:.1f}% de aprendizes (piso legal {aprendiz_min*100:.0f}%).",
        })
    elif apr > aprendiz_max:
        out.append({
            "nivel": "amarelo",
            "titulo": "Lei do Aprendiz — acima do teto",
            "msg": f"{apr*100:.1f}% de aprendizes (teto legal {aprendiz_max*100:.0f}%).",
        })
    return out


def comparativo_metricas(df_curr: pd.DataFrame, df_prev: pd.DataFrame,
                          cargos: Optional[pd.DataFrame] = None) -> list[dict]:
    def safe_pct(a, b):
        return (a - b) / b if b else 0.0
    headcount_c = len(df_curr)
    headcount_p = len(df_prev) if df_prev is not None else 0
    prov_c = float(pd.to_numeric(df_curr["proventos_total"], errors="coerce").fillna(0).sum()) if not df_curr.empty else 0
    prov_p = float(pd.to_numeric(df_prev["proventos_total"], errors="coerce").fillna(0).sum()) if not df_prev.empty else 0
    enc_c = custo_com_encargos(df_curr)
    enc_p = custo_com_encargos(df_prev) if not df_prev.empty else 0
    inat_c = pct_inativos(df_curr)
    inat_p = pct_inativos(df_prev) if not df_prev.empty else 0
    med_c = custo_medio(df_curr)
    med_p = custo_medio(df_prev) if not df_prev.empty else 0
    turn = turnover_mensal(df_curr, df_prev) if not df_prev.empty else 0
    metricas = [
        {"label": "Headcount", "atual": headcount_c, "anterior": headcount_p,
         "delta": headcount_c - headcount_p, "delta_pct": safe_pct(headcount_c, headcount_p),
         "fmt": "int", "good_direction": "up"},
        {"label": "Folha bruta", "atual": prov_c, "anterior": prov_p,
         "delta": prov_c - prov_p, "delta_pct": safe_pct(prov_c, prov_p),
         "fmt": "real", "good_direction": "neutral"},
        {"label": "Custo c/ encargos", "atual": enc_c, "anterior": enc_p,
         "delta": enc_c - enc_p, "delta_pct": safe_pct(enc_c, enc_p),
         "fmt": "real", "good_direction": "neutral"},
        {"label": "% Inativos", "atual": inat_c, "anterior": inat_p,
         "delta": inat_c - inat_p, "delta_pct": safe_pct(inat_c, inat_p),
         "fmt": "pct", "good_direction": "down"},
        {"label": "Custo médio", "atual": med_c, "anterior": med_p,
         "delta": med_c - med_p, "delta_pct": safe_pct(med_c, med_p),
         "fmt": "real", "good_direction": "neutral"},
        {"label": "Turnover", "atual": turn, "anterior": 0,
         "delta": turn, "delta_pct": 0, "fmt": "pct", "good_direction": "down"},
    ]
    return metricas


def fmt_valor(v: float, fmt: str) -> str:
    if fmt == "int":
        return f"{int(round(v))}"
    if fmt == "real":
        s = f"R$ {v:,.0f}".replace(",", ".")
        return s
    if fmt == "pct":
        return f"{v*100:.1f}%"
    return str(v)


def fmt_delta(v: float, fmt: str) -> str:
    if fmt == "int":
        return f"{v:+.0f}"
    if fmt == "real":
        sign = "+" if v >= 0 else "-"
        s = f"{sign}R$ {abs(v):,.0f}".replace(",", ".")
        return s
    if fmt == "pct":
        return f"{v*100:+.1f} p.p."
    return str(v)
