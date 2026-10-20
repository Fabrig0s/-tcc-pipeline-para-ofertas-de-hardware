import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

def executar_pipeline_ml():
    print("Carregando dados da KaBuM!...")
    df = pd.read_csv("ofertas_consolidadas.csv", sep=';') # ou o nome/sep que você usou

    if 'preco_medio_historico' not in df.columns:
        df['preco_medio_historico'] = df['preco'] * 1.15

    df['variacao_percentual'] = ((df['preco'] - df['preco_medio_historico']) / df['preco_medio_historico']) * 100


    df['tag_treino'] = df['variacao_percentual'].apply(
        lambda x: 1 if x <= -10 else (2 if x > 5 else 0) # 1: Bom, 2: Ruim, 0: Normal
    )


    X = df[['preco', 'preco_medio_historico', 'variacao_percentual']]
    y = df['tag_treino']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    

    print("Treinando o Random Forest...")
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X_train, y_train)
    

    predicoes_teste = modelo.predict(X_test)
    print(f"Acurácia do Modelo: {accuracy_score(y_test, predicoes_teste):.2f}")
    

    df['situacao_compra_cod'] = modelo.predict(X)
    mapa_tags = {1: "Bom Momento", 2: "Preço Inflacionado", 0: "Aguardar"}
    df['situacao_compra'] = df['situacao_compra_cod'].map(mapa_tags)
    

    df.to_csv("ofertas_consolidadas.csv", index=False)
    print("Pipeline de ML concluído. Base atualizada com sucesso.")

if __name__ == "__main__":
    executar_pipeline_ml()
