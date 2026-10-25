import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
import warnings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import IsolationForest

warnings.filterwarnings('ignore')
print("=== INICIANDO PIPELINE DE MACHINE LEARNING E NLP ===")

# Configuração de diretórios e gráficos
sns.set_theme(style="whitegrid")
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
pasta_graficos = os.path.join(diretorio_atual, 'graficos_artigo')
os.makedirs(pasta_graficos, exist_ok=True)

# ---------------------------------------------------------
# 1. FUNÇÃO DE LIMPEZA LEXICAL (REGEX)
# ---------------------------------------------------------
def extrair_modelo_principal(nome):
    nome = str(nome).strip()
    nome = re.split(r'\s*[-|]\s*', nome)[0] # Corta sufixos
    categorias = [
        r'teclado\s+para\s+notebook', r'teclado\s+mecan[íi]co', r'teclado\s+gamer', r'teclado',
        r'placa\s+de\s+v[íi]deo', r'placa\s+m[ãa]e', r'mem[óo]ria\s+ram', r'mem[óo]ria',
        r'fonte\s+de\s+alimenta[çc][ãa]o', r'fonte', r'gabinete\s+gamer', r'gabinete',
        r'mouse\s+gamer', r'mouse', r'headset\s+gamer', r'headset', r'monitor\s+gamer', r'monitor',
        r'ssd\s+nvme', r'ssd', r'hd\s+externo', r'disco\s+r[íi]gido',
        r'cooler\s+para\s+processador', r'water\s+cooler', r'processador', r'microfone'
    ]
    regex = r'^(?:' + '|'.join(categorias) + r')\s*'
    nome = re.sub(regex, '', nome, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', nome).strip().title()

# ---------------------------------------------------------
# 2. CARREGAMENTO DOS DADOS
# ---------------------------------------------------------
caminho_base = os.path.join(diretorio_atual, 'dados kabum (3).csv')
try:
    try:
        df_base = pd.read_csv(caminho_base, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
    except:
        df_base = pd.read_csv(caminho_base, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
    
    memoria_precos = df_base.groupby('nome_produto')['preco'].median().reset_index()
    memoria_precos.rename(columns={'preco': 'preco_referencia_base'}, inplace=True)
except FileNotFoundError:
    print(f"Erro: Base histórica não encontrada em {caminho_base}")
    exit()

caminho_hoje = os.path.join(diretorio_atual, 'ofertas_consolidadas.csv')
try:
    df_hoje = pd.read_csv(caminho_hoje, sep=';', encoding='utf-8-sig')
except FileNotFoundError:
    print("Erro: Arquivo de ofertas de hoje não encontrado.")
    exit()

# ---------------------------------------------------------
# 3. NLP - RESOLUÇÃO DE ENTIDADES (TF-IDF)
# ---------------------------------------------------------
print("Padronizando nomenclaturas com Inteligência Artificial (TF-IDF)...")
memoria_precos['nome_limpo'] = memoria_precos['nome_produto'].apply(extrair_modelo_principal)
df_hoje['nome_limpo'] = df_hoje['nome_produto'].apply(extrair_modelo_principal)

nomes_base_originais = memoria_precos['nome_produto'].tolist()
nomes_base_limpos = memoria_precos['nome_limpo'].tolist()

vetorizador = TfidfVectorizer(analyzer='word', ngram_range=(1, 2), lowercase=True)
matriz_base = vetorizador.fit_transform(nomes_base_limpos)

def buscar_produto_tfidf(linha, limite=0.45):
    vetor_pesquisa = vetorizador.transform([linha['nome_limpo']])
    similaridades = cosine_similarity(vetor_pesquisa, matriz_base)[0]
    indice_maior = np.argmax(similaridades)
    
    if similaridades[indice_maior] >= limite:
        return nomes_base_originais[indice_maior] # Retorna o nome exato da base para o merge
    return linha['nome_produto'] # Produto novo

df_hoje['nome_produto_padronizado'] = df_hoje.apply(buscar_produto_tfidf, axis=1)

# ---------------------------------------------------------
# 4. CRUZAMENTO E ENGENHARIA DE ATRIBUTOS
# ---------------------------------------------------------
df = df_hoje.merge(memoria_precos[['nome_produto', 'preco_referencia_base']], 
                   left_on='nome_produto_padronizado', 
                   right_on='nome_produto', 
                   how='left')

produtos_novos = df['preco_referencia_base'].isna()
df.loc[produtos_novos, 'preco_referencia_base'] = df.loc[produtos_novos, 'preco'] 
df['variacao_vs_base'] = ((df['preco'] - df['preco_referencia_base']) / df['preco_referencia_base']) * 100

# ---------------------------------------------------------
# 5. DETECÇÃO DE ANOMALIAS (ISOLATION FOREST)
# ---------------------------------------------------------
print("Treinando modelo de detecção de anomalias (Isolation Forest)...")
df['outlier_ml'] = False
df_treino = df[~produtos_novos]

if len(df_treino) > 10:
    X_precos = df_treino[['variacao_vs_base']].values
    modelo_if = IsolationForest(contamination=0.02, random_state=42)
    previsoes = modelo_if.fit_predict(X_precos)
    df.loc[~produtos_novos, 'outlier_ml'] = previsoes == -1

# ---------------------------------------------------------
# 6. REGRAS DE NEGÓCIO E CLASSIFICAÇÃO
# ---------------------------------------------------------
MARGEM = 10.0
df['situacao_compra'] = 'Sem Histórico (Novo)'
df.loc[~produtos_novos, 'situacao_compra'] = 'Preço Médio'
df.loc[(~produtos_novos) & (df['variacao_vs_base'] <= -MARGEM), 'situacao_compra'] = 'Boa Compra'
df.loc[(~produtos_novos) & (df['variacao_vs_base'] >= MARGEM), 'situacao_compra'] = 'Evitar'
df.loc[df['outlier_ml'], 'situacao_compra'] = 'Anomalia (Isolada por IA)'

# ---------------------------------------------------------
# 7. EXPORTAÇÃO E VISUALIZAÇÃO
# ---------------------------------------------------------
# Garante que o nome original da oferta não se perca no CSV
df.rename(columns={'nome_produto_x': 'nome_oferta_original'}, inplace=True)

colunas_finais = [
    'nome_produto_padronizado', 'nome_oferta_original', 'nome_loja', 
    'preco', 'preco_referencia_base', 'variacao_vs_base', 
    'situacao_compra', 'url_oferta'
]
df_final = df[colunas_finais].sort_values(by=['nome_produto_padronizado', 'preco'])

caminho_final = os.path.join(diretorio_atual, 'dados_enriquecidos_ia.csv')
df_final.to_csv(caminho_final, sep=';', index=False, encoding='utf-8-sig')

print(f"\n[SUCESSO] Processamento concluído!")
print(f" -> Tabela estruturada salva em: {caminho_final}")


# ---------------------------------------------------------
# 8. GERAÇÃO DE GRÁFICOS PARA O ARTIGO (QUALIS)
# ---------------------------------------------------------
print("Gerando gráficos finais para o artigo...")

# Gráfico 1: Distribuição das Recomendações
plt.figure(figsize=(10, 5))
cores = {'Boa Compra': '#2ca02c', 'Preço Médio': '#1f77b4', 'Evitar': '#ff7f0e', 
         'Anomalia (Isolada por IA)': '#d62728', 'Sem Histórico (Novo)': '#7f7f7f'}
ax = sns.countplot(data=df, x='situacao_compra', palette=cores, 
                   order=['Boa Compra', 'Preço Médio', 'Evitar', 'Anomalia (Isolada por IA)', 'Sem Histórico (Novo)'])
plt.title('Diagnóstico de Preços via Machine Learning e NLP', fontsize=14, fontweight='bold')
plt.ylabel('Volume de Ofertas', fontsize=12)
plt.xlabel('Classificação do Algoritmo', fontsize=12)
plt.xticks(rotation=15)
for p in ax.patches:
    ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                ha='center', va='center', xytext=(0, 5), textcoords='offset points')
plt.tight_layout()
plt.savefig(os.path.join(pasta_graficos, 'figura1_classificacao_final.png'), dpi=300)
plt.close()