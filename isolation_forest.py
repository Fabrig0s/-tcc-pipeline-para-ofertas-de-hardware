
import pandas as pd
import glob
import os
from sklearn.ensemble import IsolationForest
import sys
import re

def extrair_modelo_principal(nome):
    """Remove apenas a categoria genérica do início, preservando o modelo e as especificações."""
    nome = str(nome).strip()
    
    categorias = [
        r'teclado\s+para\s+notebook', r'teclado\s+mecan[íi]co', r'teclado\s+gamer', r'teclado',
        r'placa\s+de\s+v[íi]deo', r'placa\s+m[ãa]e', r'mem[óo]ria\s+ram', r'mem[óo]ria',
        r'fonte\s+de\s+alimenta[çc][ãa]o', r'fonte', r'gabinete\s+gamer', r'gabinete',
        r'mouse\s+gamer', r'mouse', r'headset\s+gamer', r'headset', r'monitor\s+gamer', r'monitor',
        r'ssd\s+nvme', r'ssd', r'hd\s+externo', r'disco\s+r[íi]gido',
        r'cooler\s+para\s+processador', r'water\s+cooler', r'processador', r'microfone'
    ]
    
    # Esta nova regra remove a categoria e também apaga o hífen se ele vier imediatamente após a categoria
    regex = r'^(?:' + '|'.join(categorias) + r')\s*(?:[-|]\s*)?'
    
    nome_limpo = re.sub(regex, '', nome, flags=re.IGNORECASE)
    nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip().title()
    
    # Trava de segurança: Se a limpeza deixar o nome vazio, retorna o original formatado
    if not nome_limpo or nome_limpo == '-':
        return nome.title()
        
    return nome_limpo


# 1. INGESTÃO EM LOTE (Lendo múltiplas planilhas individuais)
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
pasta_historico = os.path.join(diretorio_atual, 'historico_semana')

# Cria a pasta automaticamente se ela não existir
os.makedirs(pasta_historico, exist_ok=True)

arquivos_historico = glob.glob(os.path.join(pasta_historico, "*.csv"))

# Trava de segurança: Verifica se encontrou arquivos
if not arquivos_historico:
    print(f"[ERRO] Nenhum arquivo CSV encontrado na pasta: {pasta_historico}")
    print("Por favor, coloque as planilhas dos dias anteriores lá dentro e rode novamente.")
    sys.exit()

lista_dataframes = []

for arquivo in arquivos_historico:
    try:
        df_dia = pd.read_csv(arquivo, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
        if len(df_dia.columns) < 2: # Tenta com vírgula se ponto-e-vírgula falhar
            df_dia = pd.read_csv(arquivo, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
        lista_dataframes.append(df_dia)
        print(f"Lido com sucesso: {os.path.basename(arquivo)}")
    except Exception as e:
        print(f"Erro ao ler {os.path.basename(arquivo)}: {e}")

df_historico_consolidado = pd.concat(lista_dataframes, ignore_index=True)
print(f"\n[SUCESSO] {len(lista_dataframes)} planilhas combinadas. Total de linhas: {len(df_historico_consolidado)}")

df_historico_consolidado['nome_produto_padronizado'] = df_historico_consolidado['nome_produto'].apply(extrair_modelo_principal)

resumo_semanal = df_historico_consolidado.groupby('nome_produto_padronizado').agg(
    preco_medio_semana=('preco', 'mean'),
    volatilidade_semana=('preco', 'std') # Calcula a instabilidade do preço nos últimos dias
).reset_index()

# Preenche com 0 a volatilidade de produtos que não mudaram de preço
resumo_semanal['volatilidade_semana'] = resumo_semanal['volatilidade_semana'].fillna(0)

# 3. CRUZAMENTO COM O DIA ATUAL (A "Planilha Nova")
caminho_hoje = os.path.join(diretorio_atual, 'ofertas_hoje.csv')

try:
    df_novo = pd.read_csv(caminho_hoje, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
    if len(df_novo.columns) < 2:
        df_novo = pd.read_csv(caminho_hoje, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
except FileNotFoundError:
    print(f"[ERRO] O ficheiro {caminho_hoje} não foi encontrado.")
    sys.exit()

# Aplica a limpeza também na planilha nova para o merge funcionar perfeitamente
df_novo['nome_produto_padronizado'] = df_novo['nome_produto'].apply(extrair_modelo_principal)

# Une os dados de hoje com o resumo da semana
df_analise = df_novo.merge(resumo_semanal, on='nome_produto_padronizado', how='left')

# Calcula o quanto o preço de hoje desviou da média da semana
df_analise['variacao_vs_semana'] = ((df_analise['preco'] - df_analise['preco_medio_semana']) / df_analise['preco_medio_semana']) * 100

# 4. MOTOR DE IA (Isolation Forest)
df_treino = df_analise.dropna(subset=['preco_medio_semana'])

if len(df_treino) > 10:
    # A IA avalia a Variação de Hoje cruzada com a Volatilidade da Semana
    X = df_treino[['variacao_vs_semana', 'volatilidade_semana']].values
    
    modelo_if = IsolationForest(contamination=0.02, random_state=42)
    df_analise.loc[df_treino.index, 'outlier_ml'] = modelo_if.fit_predict(X) == -1

# ---------------------------------------------------------
# 4.5. REGRAS DE NEGÓCIO E CLASSIFICAÇÃO FINAL
# ---------------------------------------------------------
# Cria a coluna com um valor padrão
df_analise['situacao_compra'] = 'Sem Histórico'

# Se a Inteligência Artificial rodou com sucesso e criou a marcação de anomalia:
if 'outlier_ml' in df_analise.columns:
    df_analise.loc[df_analise['outlier_ml'] == False, 'situacao_compra'] = 'Comportamento Normal'
    
    # Separa as anomalias detectadas entre fraudes/aumentos e super promoções
    df_analise.loc[(df_analise['outlier_ml'] == True) & (df_analise['variacao_vs_semana'] < 0), 'situacao_compra'] = 'Anomalia (Super Promoção)'
    df_analise.loc[(df_analise['outlier_ml'] == True) & (df_analise['variacao_vs_semana'] > 0), 'situacao_compra'] = 'Anomalia (Preço Abusivo)'


# ---------------------------------------------------------
# 5. EXPORTAÇÃO E VISUALIZAÇÃO DOS RESULTADOS
# ---------------------------------------------------------
print("\n=== DIAGNÓSTICO DA INTELIGÊNCIA ARTIFICIAL ===")
print(df_analise['situacao_compra'].value_counts())

# Filtra apenas as colunas que importam para a análise final
colunas_desejadas = [
    'nome_produto_padronizado', 'nome_produto', 'nome_loja', 
    'preco', 'preco_medio_semana', 'variacao_vs_semana', 
    'volatilidade_semana', 'situacao_compra'
]

# Garante que não vai dar erro se alguma coluna extra (como url_oferta) estiver faltando
colunas_finais = [c for c in colunas_desejadas if c in df_analise.columns]

# Organiza a tabela para que as "Anomalias" e "Boas Compras" fiquem no topo
df_final = df_analise[colunas_finais].sort_values(by=['situacao_compra', 'variacao_vs_semana'])

# --- ADICIONE ESTAS LINHAS AQUI ---
# Arredonda as colunas matemáticas para 2 casas decimais
colunas_para_arredondar = ['preco', 'preco_medio_semana', 'variacao_vs_semana', 'volatilidade_semana']

for col in colunas_para_arredondar:
    if col in df_final.columns:
        df_final[col] = df_final[col].round(2)
# ---------------------------------

# Salva o arquivo CSV definitivo (mantendo a vírgula para o Excel brasileiro)
caminho_final = os.path.join(diretorio_atual, 'resultado_isolation_forest.csv')
df_final.to_csv(caminho_final, sep=';', index=False, encoding='utf-8-sig', decimal=',')

print(f"\n[SUCESSO] O arquivo com o julgamento final da IA foi salvo em: {caminho_final}")