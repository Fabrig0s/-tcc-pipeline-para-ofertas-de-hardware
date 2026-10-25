# -*- coding: utf-8 -*-
"""
Script de tratamento (Transform) adaptado para Supabase (PostgreSQL).

Lê as tabelas utilizando a API REST do Supabase (com paginação para 
contornar o limite padrão de 1000 linhas), recalcula os atributos 
derivados utilizando o Pandas e devolve os dados através de UPSERT 
(em lotes) para evitar limites de payload.
"""

import os
import pandas as pd
from supabase import create_client, Client

# ---------------------------------------------------------------------
# CONFIGURAÇÃO SUPABASE
# ---------------------------------------------------------------------
# Recomenda-se utilizar variáveis de ambiente por segurança
SUPABASE_URL = os.environ.get("SUPABASE_URL", "postgresql://postgres.pxetpadnjpcvvmqlqvzg:Tcc%402026!dd@aws-0-us-east-1.pooler.supabase.com:5432/postgres")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "Tcc%402026!dd")

TABELA_PRODUTO = "produtos"
TABELA_LOJA = "lojas"
TABELA_OFERTA = "ofertas"

MARGEM_SITUACAO = 0.10
LIMITE_OUTLIER = 0.30

COLUNAS_OFERTA = [
    "id_oferta", "id_produto", "id_loja", "preco",
    "preco_medio_historico", "outlier", "situacao_compra",
    "url_oferta", "data_coleta",
]

# ---------------------------------------------------------------------
# FUNÇÕES DE COMUNICAÇÃO COM SUPABASE
# ---------------------------------------------------------------------
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_all(supabase: Client, table_name: str) -> pd.DataFrame:
    """Lê todos os registos da tabela contornando o limite de 1000 linhas da API REST."""
    all_records = []
    limit = 1000
    offset = 0
    
    while True:
        response = supabase.table(table_name).select("*").range(offset, offset + limit - 1).execute()
        data = response.data
        all_records.extend(data)
        
        if len(data) < limit:
            break
        offset += limit
        
    return pd.DataFrame(all_records)

def upsert_em_lotes(supabase: Client, table_name: str, df: pd.DataFrame, chunk_size=500):
    """Envia os dados de volta para o Supabase em lotes (chunks) para evitar timeouts."""
    if df.empty:
        return
        
    # Converte tipos datetime para string (ISO) para evitar erros de serialização JSON
    for col in df.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]']).columns:
        df[col] = df[col].astype(str)
        
    # Substitui pd.NA e NaN do Pandas por None (nulo no formato JSON)
    df = df.where(pd.notnull(df), None)
    
    records = df.to_dict(orient="records")
    
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        supabase.table(table_name).upsert(chunk).execute()


# ---------------------------------------------------------------------
# PADRONIZAÇÃO DE LOJA E IDENTIFICAÇÃO DE MARCA
# ---------------------------------------------------------------------
MAPA_LOJAS = {
    "kabum": "KaBuM!",
    "kabum!": "KaBuM!",
    "pichau": "Pichau",
    "terabyte": "Terabyte",
    "amazon": "Amazon",
}

MAPA_MARCAS = {
    "redragon": "Redragon",
    "asus": "ASUS",
    "gigabyte": "Gigabyte",
    "msi": "MSI",
    "nvidia": "NVIDIA",
    "amd": "AMD",
    "intel": "Intel",
    "corsair": "Corsair",
    "kingston": "Kingston",
    "galax": "Galax",
}

def padronizar_loja(nome):
    if nome is None or pd.isna(nome):
        return nome
    chave = str(nome).strip().lower()
    return MAPA_LOJAS.get(chave, str(nome).strip().title())

def identificar_marca(nome_produto):
    if nome_produto is None or pd.isna(nome_produto):
        return None
    nome = str(nome_produto).lower()
    for palavra, marca in MAPA_MARCAS.items():
        if palavra in nome:
            return marca
    return None


def atualizar_produto_marca(supabase: Client):
    df = fetch_all(supabase, TABELA_PRODUTO)
    if df.empty:
        return

    df["marca"] = df["nome_produto"].apply(identificar_marca)
    upsert_em_lotes(supabase, TABELA_PRODUTO, df)

    qtd_identificadas = df["marca"].notna().sum()
    print(f"PRODUTO: marca identificada em {qtd_identificadas} de {len(df)} produto(s).")


def atualizar_loja_padronizada(supabase: Client):
    df = fetch_all(supabase, TABELA_LOJA)
    if df.empty:
        return

    df["nome_loja"] = df["nome_loja"].apply(padronizar_loja)
    upsert_em_lotes(supabase, TABELA_LOJA, df)

    print(f"LOJA: {len(df)} nome(s) de loja padronizado(s).")


# ---------------------------------------------------------------------
# OUTLIER E SITUAÇÃO DE COMPRA
# ---------------------------------------------------------------------
def verificar_outlier(preco, media):
    if media is None or pd.isna(media) or media == 0:
        return False
    variacao = abs(preco - media) / media
    return bool(variacao > LIMITE_OUTLIER)

def classificar_compra(preco, media):
    if media is None or pd.isna(media) or media == 0:
        return "Sem histórico"
    percentual = preco / media
    if percentual <= 1 - MARGEM_SITUACAO:
        return "Boa compra"
    elif percentual <= 1 + MARGEM_SITUACAO:
        return "Preço médio"
    else:
        return "Evitar"

def calcular_tratamento(df: pd.DataFrame) -> pd.DataFrame:
    # Garante que a data é tratada como datetime para a ordenação correta
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])
    df = df.sort_values(["id_produto", "data_coleta"]).reset_index(drop=True)

    df["preco_medio_historico"] = None
    df["outlier"] = False
    df["situacao_compra"] = "Sem histórico"

    for id_produto, grupo in df.groupby("id_produto", sort=False):
        grupo = grupo.sort_values("data_coleta")
        precos_anteriores = []

        for idx, row in grupo.iterrows():
            preco_atual = row["preco"]

            if not precos_anteriores:
                df.at[idx, "preco_medio_historico"] = None
                df.at[idx, "outlier"] = False
                df.at[idx, "situacao_compra"] = "Sem histórico"
            else:
                media = sum(precos_anteriores) / len(precos_anteriores)
                is_outlier = verificar_outlier(preco_atual, media)
                situacao = classificar_compra(preco_atual, media)

                df.at[idx, "preco_medio_historico"] = media
                df.at[idx, "outlier"] = is_outlier
                df.at[idx, "situacao_compra"] = situacao

            if not df.at[idx, "outlier"]:
                precos_anteriores.append(preco_atual)

    return df

def main():
    supabase = get_supabase_client()

    print("Atualizando marca dos produtos...")
    atualizar_produto_marca(supabase)

    print("Padronizando nomes de loja...")
    atualizar_loja_padronizada(supabase)

    print("\nLendo ofertas do Supabase...")
    df = fetch_all(supabase, TABELA_OFERTA)

    if df.empty:
        print("Nenhuma oferta encontrada na tabela. Nada a tratar.")
        return

    print(f"{len(df)} oferta(s) encontradas, de {df['id_produto'].nunique()} produto(s) distintos.")

    resultado = calcular_tratamento(df)
    resultado = resultado[COLUNAS_OFERTA]

    print("Enviando os resultados calculados para o Supabase (UPSERT)...")
    upsert_em_lotes(supabase, TABELA_OFERTA, resultado)

    resumo = resultado["situacao_compra"].value_counts()
    qtd_outliers = int(resultado["outlier"].sum())

    print("\nTratamento concluído com sucesso.")
    print(f"Outliers identificados: {qtd_outliers}")
    print("Situação de compra:")
    for situacao, qtd in resumo.items():
        print(f"  {situacao}: {qtd}")

if __name__ == "__main__":
    main()