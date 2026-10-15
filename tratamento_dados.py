import pandas as pd

def simular_tratamento():
    print("Iniciando tratamento de dados (Mock)...")
    # Lê o que a extração gerou
    df = pd.read_csv("ofertas_kabum.csv")
    
    # Aqui a sua equipe fará a limpeza real, remoção de nulos, outliers, etc.
    # Por enquanto, apenas repassa o arquivo para o modelo de ML consumir
    
    df.to_csv("dados_tratados_prontos_para_ml.csv", index=False)
    print("Tratamento concluído. Repassando para a Camada de Inteligência.")

if __name__ == "__main__":
    simular_tratamento()