import sys
import requests
import time
import os
import cv2
import json
import pickle
import base64
import threading
from datetime import datetime

# --- Configurações ---

# Verifica se o argumento foi passado, senão define padrão 0
TEMPO_ESPERA = float(sys.argv[1])

print(f"Tempo de espera entre disparos: {TEMPO_ESPERA}")
ARQUIVO_SAIDA = f"resultados_fixo_{TEMPO_ESPERA}.csv"
NEVOA_IP = "10.81.24.151"
OPENFAAS_URL = f"http://{NEVOA_IP}:31112/function/crowdcount-yolo"
DATASET_PATH = "/home/rafael/Desktop/quarto_ano/TCC/Dataset/frames/"

# Listar fotos
try:
    fotos = sorted(os.listdir(DATASET_PATH))
except FileNotFoundError:
    print(f"Diretório {DATASET_PATH} não encontrado. Criando lista vazia para teste.")
    fotos = []

# --- Variáveis Globais e Locks ---
csv_lock = threading.Lock() # Lock para escrita segura no arquivo

# --- Preparação do Arquivo CSV ---
# Reinicia o arquivo a cada execução ou mantém append? 
# O código original usava 'w' se não existisse, mas aqui vamos garantir o cabeçalho novo.
if not os.path.exists(ARQUIVO_SAIDA):
    with open(ARQUIVO_SAIDA, 'w') as f:
        # Cabeçalho atualizado conforme solicitado
        f.write("imagem,iteracao,duracao_req,tempo_execução,total_faces_detectadas\n")

# --- Funções de Serialização (Mantidas compatíveis com faas.py) ---
def serialize(imgpath):
    img = cv2.imread(imgpath)
    imgdata = pickle.dumps(img)
    imserial = {'image_data' : base64.b64encode(imgdata).decode('ascii')}
    return imserial

def construct_json(imserial):
    data = {'data' : imserial}
    json_data = json.dumps(data)
    return json_data

# --- Função da Thread de Processamento ---
def processar_foto_em_thread(foto_nome, foto_path, session, iteracao_atual):
    try:
        imserial = serialize(foto_path)
        img_json = construct_json(imserial)
        
        # Marca o tempo de início da requisição (Client Side)
        start_req = time.time()
        
        # Envio da requisição
        response = session.post(OPENFAAS_URL, data=img_json, timeout=60)
        
        # Marca o tempo de fim da requisição
        end_req = time.time()
        duracao_req = end_req - start_req # Tempo total de ida e volta
        
        # Processa a resposta JSON do faas.py
        # Esperado: {"person_count": <int>, "elapsed": <float>}
        if response.status_code == 200:
            resp_data = response.json()
            
            # Se o retorno vier como string JSON (dependendo da versão do flask/faas), fazemos parse duplo
            if isinstance(resp_data, str):
                resp_data = json.loads(resp_data)

            faces = resp_data.get('person_count', 0)
            tempo_execucao_server = resp_data.get('elapsed', 0.0) # Tempo de inferência no servidor
            
            # Escrita no CSV (Thread Safe)
            with csv_lock:
                with open(ARQUIVO_SAIDA, 'a') as f:
                    f.write(f"{foto_nome},{iteracao_atual},{duracao_req:.4f},{tempo_execucao_server:.4f},{faces}\n")
            
            print(f"[Iter {iteracao_atual}] {foto_nome}: {faces} faces | Req: {duracao_req:.2f}s | Inferência: {tempo_execucao_server:.2f}s")
            
        else:
            print(f"Erro {response.status_code} ao processar {foto_nome}: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Erro de HTTP processando {foto_nome}: {e}")
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON de {foto_nome}: {e}. Resposta crua: {response.text}")
    except Exception as e:
        print(f"Erro inesperado na thread ({foto_nome}): {e}")

# --- Loop Principal ---
print("Iniciando disparos em lote (Coleta por imagem)...")

with requests.Session() as session:
    # Loop de 5 iterações (conforme original)
    for i in range(5):
        print(f"--- Iniciando Iteração {i} ---")
        
        threads_da_iteracao = []
        
        # Dispara todas as threads da iteração
        for foto in fotos:
            foto_completa = os.path.join(DATASET_PATH, foto)
            
            # Passamos 'foto' (nome do arquivo) e 'i' (numero da iteração) para logar
            t = threading.Thread(target=processar_foto_em_thread, args=(foto, foto_completa, session, i))
            threads_da_iteracao.append(t)
            t.start()
            
            # Aguarda o tempo configurado entre disparos
            time.sleep(TEMPO_ESPERA)

        # Aguarda todas as requisições dessa iteração terminarem antes de começar a próxima iteração
        # (Isso mantém a lógica de "lotes", se quiser fluxo contínuo total, remova este bloco join)
        for t in threads_da_iteracao:
            t.join()

        print(f"Iteração {i} concluída.")

print("Processo finalizado.")
