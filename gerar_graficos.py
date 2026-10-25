import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Configuração da estética académica
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12})

# Carregar os resultados
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_csv = os.path.join(diretorio_atual, 'resultado_isolation_forest.csv')

df = pd.read_csv(caminho_csv, sep=';', decimal=',')

# ---------------------------------------------------------
# Gráfico 1: Distribuição das Anomalias (Gráfico de Tarte)
# ---------------------------------------------------------
plt.figure(figsize=(8, 6))
contagem = df['situacao_compra'].value_counts()
cores = ['#2ecc71', '#95a5a6', '#e74c3c', '#3498db']

plt.pie(contagem, labels=contagem.index, autopct='%1.1f%%', colors=cores, startangle=140)
plt.title('Distribuição da Classificação de Ofertas pelo Isolation Forest', pad=20, fontweight='bold')
caminho_grafico_1 = os.path.join(diretorio_atual, 'grafico_distribuicao_ofertas.png')
plt.savefig(caminho_grafico_1, dpi=300, bbox_inches='tight')
plt.close()

# ---------------------------------------------------------
# Gráfico 2: Dispersão (Volatilidade vs. Variação de Preço)
# ---------------------------------------------------------
plt.figure(figsize=(10, 6))

# Filtrar produtos com histórico válido para visualização
df_plot = df[df['situacao_compra'] != 'Sem Histórico']

sns.scatterplot(
    data=df_plot, 
    x='volatilidade_semana', 
    y='variacao_vs_semana', 
    hue='situacao_compra',
    palette={'Comportamento Normal': '#2ecc71', 'Anomalia (Super Promoção)': '#3498db', 'Anomalia (Preço Abusivo)': '#e74c3c'},
    alpha=0.7,
    s=80
)

plt.axhline(0, color='black', linestyle='--', linewidth=1)
plt.title('Deteção de Outliers: Volatilidade vs. Variação de Preço Diária', fontweight='bold')
plt.xlabel('Volatilidade da Semana (Desvio Padrão em R$)')
plt.ylabel('Variação do Preço Hoje (%)')
plt.legend(title='Classificação da IA', bbox_to_anchor=(1.05, 1), loc='upper left')

caminho_grafico_2 = os.path.join(diretorio_atual, 'grafico_dispersao_ia.png')
plt.savefig(caminho_grafico_2, dpi=300, bbox_inches='tight')
plt.close()

print("[SUCESSO] Imagens geradas e guardadas na pasta do projeto.")