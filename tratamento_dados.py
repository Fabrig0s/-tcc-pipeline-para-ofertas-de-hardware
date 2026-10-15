import pandas as pd

def simular_tratamento():
    print("Iniciando tratamento de dados (Mock)...")

    df = pd.read_csv("ofertas_kabum.csv", sep=';')
    
    df.to_csv("dados_tratados_prontos_para_ml.csv", index=False)
    print("Tratamento concluído. Repassando para a Camada de Inteligência.")

if __name__ == "__main__":
    simular_tratamento()