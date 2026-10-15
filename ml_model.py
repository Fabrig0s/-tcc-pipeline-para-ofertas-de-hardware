import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

def executar_pipeline_ml():
    # 1. Carregar a tabela da KaBuM! (ajuste o caminho do seu CSV local/mock)
    print("Carregando dados da KaBuM!...")
    df = pd.read_csv("kabum_ofertas.csv")
    
    # 2. Engenharia de Features (Simulando métricas que o modelo usará)
    # Exemplo: calculando a diferença percentual entre o preço atual e a média histórica
    df['variacao_percentual'] = ((df['preco'] - df['preco_medio_historico']) / df['preco_medio_historico']) * 100
    
    # Criando a tag alvo (Target) baseada em uma regra de negócio inicial para treinar o modelo
    # Se estiver 10% mais barato que a média, é "Bom Momento". Se estiver acima, "Inflacionado".
    df['tag_treino'] = df['variacao_percentual'].apply(
        lambda x: 1 if x <= -10 else (2 if x > 5 else 0) # 1: Bom, 2: Ruim, 0: Normal
    )

    # 3. Separar Features (X) e Target (y)
    X = df[['preco', 'preco_medio_historico', 'variacao_percentual']]
    y = df['tag_treino']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. Treinar o Random Forest
    print("Treinando o Random Forest...")
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X_train, y_train)
    
    # 5. Avaliar e Aplicar
    predicoes_teste = modelo.predict(X_test)
    print(f"Acurácia do Modelo: {accuracy_score(y_test, predicoes_teste):.2f}")
    
    # Aplicar as predições na base total e mapear para texto legível para o Dashboard
    df['situacao_compra_cod'] = modelo.predict(X)
    mapa_tags = {1: "Bom Momento", 2: "Preço Inflacionado", 0: "Aguardar"}
    df['situacao_compra'] = df['situacao_compra_cod'].map(mapa_tags)
    
    # Salvar o resultado final que será lido pelo Power BI / Banco de Dados
    df.to_csv("kabum_analisado.csv", index=False)
    print("Pipeline de ML concluído. Base atualizada com sucesso.")

if __name__ == "__main__":
    executar_pipeline_ml()