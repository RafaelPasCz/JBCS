import sys
import requests
import time
import os
import cv2
import json
import pickle
import base64
import threading
import serial
from datetime import datetime

# --- CONFIGURAÇÕES ---
SERIAL_PORT = '/dev/ttyUSB0'  
BAUDRATE = 115200

# Configurações do FaaS
ROOT_PATH = '/home/rafael/Desktop/quarto_ano/TCC' 
IMG_PATH = ROOT_PATH + '/Dataset/frames/seq_000001.jpg'
URL_FAAS = 'http://10.81.24.54:8080/function/crowdcount-yolo'

# Configurações do Experimento
TOTAL_ITERACOES = 7
IGNORAR_INICIAIS = 2 # Cold start
ARQUIVO_SAIDA = "resultado_faas_corrigido.csv"

# --- VARIÁVEIS GLOBAIS E LOCKS ---
stop_serial = False
serial_data_lock = threading.Lock()
# Acumulador de energia
energy_shared_data = {"total_mWh": 0.0}

# --- FUNÇÕES DE IMAGEM ---
def serialize(imgpath):
    if not os.path.exists(imgpath):
        raise FileNotFoundError(f"Imagem não encontrada: {imgpath}")
    img = cv2.imread(imgpath)
    imgdata = pickle.dumps(img, protocol=0) 
    imserial = {'image_data' : base64.b64encode(imgdata).decode('ascii')}
    return imserial

def construct_json(imserial):
    data = {'data' : imserial}
    json_data = json.dumps(data)
    return json_data

# --- THREAD DE MONITORAMENTO (Lógica do tvbox.py) ---
def monitor_serial():
    global stop_serial
    
    # Zera acumulador
    with serial_data_lock:
        energy_shared_data["total_mWh"] = 0.0

    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1) as ser:
            ser.reset_input_buffer()
            
            # Variável para guardar o timestamp anterior (do Arduino)
            prev_device_timestamp = None
            
            while not stop_serial:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        # Adaptação da lógica do tvbox.py
                        parts = line.split(";") # <-- CORREÇÃO: Ponto e vírgula
                        
                        if len(parts) >= 3:
                            # Parse dos dados conforme tvbox.py
                            dev_timestamp = int(parts[0]) # Timestamp do device (ms)
                            current = float(parts[1])     # Corrente
                            voltage = float(parts[2])     # Tensão
                            
                            # Cálculo de Potência (tvbox.py: P = V * I)
                            # Assumindo que o resultado disso é mW (conforme seu código original)
                            power_mW = current * voltage 
                            
                            # Integração de Energia usando timestamp do dispositivo
                            if prev_device_timestamp is not None:
                                delta_ms = dev_timestamp - prev_device_timestamp
                                
                                # Filtro de segurança (tvbox.py)
                                if 0 < delta_ms < 2000:
                                    # E(mWh) = P(mW) * t(ms) / 3600000
                                    inc_mwh = (power_mW * delta_ms) / 3600000.0
                                    
                                    with serial_data_lock:
                                        energy_shared_data["total_mWh"] += inc_mwh
                            
                            # Atualiza timestamp anterior
                            prev_device_timestamp = dev_timestamp
                            
                except ValueError:
                    continue # Ignora erro de conversão
                except IndexError:
                    continue # Ignora linha incompleta
                except Exception as e:
                    # Evita que a thread morra por erro bobo, apenas imprime
                    # print(f"Erro no loop serial: {e}") 
                    pass

    except serial.SerialException as e:
        print(f"Erro Crítico na Serial: {e}")

# --- EXECUÇÃO PRINCIPAL ---
def main():
    global stop_serial
    print(f"--- Iniciando Experimento (Lógica tvbox.py) ---")
    
    # 1. Preparação da Imagem
    try:
        imserial = serialize(IMG_PATH)
        json_payload = construct_json(imserial)
        print("Imagem pronta.")
    except Exception as e:
        print(f"Erro imagem: {e}")
        return

    # 2. Prepara CSV
    if not os.path.exists(ARQUIVO_SAIDA):
        with open(ARQUIVO_SAIDA, 'w', newline='') as f:
            f.write("iteracao,status,pessoas_detectadas,tempo_req_client_s,tempo_proc_server_s,energia_mWh\n")

    # 3. Loop de Requisições
    for i in range(TOTAL_ITERACOES):
        iteracao_num = i + 1
        is_warmup = iteracao_num <= IGNORAR_INICIAIS
        label = "WARMUP" if is_warmup else "GRAVANDO"
        
        print(f"\n--- Req {iteracao_num}/{TOTAL_ITERACOES} [{label}] ---")

        # A. Inicia a Thread Serial
        stop_serial = False
        thread_energia = threading.Thread(target=monitor_serial)
        thread_energia.start()

        # B. Requisição HTTP (Cronômetro Client)
        start_client = time.time()
        
        try:
            response = requests.post(URL_FAAS, data=json_payload)
            _ = response.content # Garante download completo
            end_client = time.time()

            # C. Para a Serial IMEDIATAMENTE
            stop_serial = True
            thread_energia.join()

            # D. Cálculos
            tempo_req_client = end_client - start_client
            
            with serial_data_lock:
                energia_total = energy_shared_data["total_mWh"]

            # Parsing Resposta
            txt = response.text.strip()
            if '\n' in txt: txt = txt.split('\n')[-1] # Limpa logs extras
            
            try:
                resp_json = json.loads(txt)
                if isinstance(resp_json, str): resp_json = json.loads(resp_json)
                
                pessoas = resp_json.get('person_count', 0)
                tempo_proc_server = resp_json.get('elapsed', 0.0)
            except:
                pessoas = -1
                tempo_proc_server = -1

            print(f"  > Pessoas: {pessoas}")
            print(f"  > T. Client: {tempo_req_client:.4f}s | T. Server: {tempo_proc_server}s")
            print(f"  > Energia: {energia_total:.6f} mWh")

            # E. Salva CSV
            if not is_warmup:
                with open(ARQUIVO_SAIDA, 'a', newline='') as f:
                    line = f"{iteracao_num},valid,{pessoas},{tempo_req_client:.4f},{tempo_proc_server},{energia_total:.6f}\n"
                    f.write(line)
                print("  > Salvo.")
            else:
                print("  > Ignorado.")

        except Exception as e:
            stop_serial = True
            thread_energia.join()
            print(f"  > FALHA: {e}")
            time.sleep(1)

        time.sleep(2) # Pausa entre iterações

    print(f"\nFim. Dados em: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    main()