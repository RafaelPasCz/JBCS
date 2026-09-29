import time
import os
import glob
import csv
from datetime import datetime

# --- Configurações ---
ARQUIVO_SAIDA = "consumo_rapl_por_minuto.csv"
DURACAO_MINUTO = 60  # Segundos por ciclo
TOTAL_CICLOS = 5     # Quantas vezes vai repetir

def get_rapl_path():
    """
    Busca o caminho do arquivo de energia (energy_uj) do RAPL.
    Tenta o 'package-0' (processador inteiro) padrão.
    """
    # Caminhos comuns para Intel/AMD RAPL
    paths = [
        "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj",
        "/sys/class/powercap/intel-rapl:0/energy_uj"
    ]
    
    for path in paths:
        if os.path.exists(path):
            return path
            
    # Fallback: tenta encontrar via glob se o nome da pasta variar
    found = glob.glob("/sys/class/powercap/intel-rapl/intel-rapl:*/energy_uj")
    if found:
        return found[0]
        
    return None

def read_energy_uj(path):
    """Lê o valor acumulado em microjoules."""
    try:
        with open(path, 'r') as f:
            return int(f.read().strip())
    except Exception as e:
        print(f"Erro ao ler RAPL: {e}")
        return 0

def monitorar_rapl():
    rapl_file = get_rapl_path()
    
    if not rapl_file:
        print("ERRO: Interface RAPL não encontrada.")
        print("Verifique se está no Linux e se o módulo 'intel_rapl' está carregado.")
        return

    print(f"--- Iniciando Monitor RAPL (Interno) ---")
    print(f"Lendo de: {rapl_file}")
    print(f"Ciclos: {TOTAL_CICLOS} de {DURACAO_MINUTO}s cada.")
    print(f"Saída: {ARQUIVO_SAIDA}")

    # Cria o CSV com cabeçalho se não existir
    if not os.path.exists(ARQUIVO_SAIDA):
        with open(ARQUIVO_SAIDA, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_registro", "ciclo", "energia_mWh", "potencia_media_mW"])

    try:
        for ciclo in range(1, TOTAL_CICLOS + 1):
            print(f"\nIniciando Ciclo {ciclo}/{TOTAL_CICLOS}...")
            
            # 1. Leitura Inicial
            t_start = time.time()
            e_start_uj = read_energy_uj(rapl_file)
            
            # 2. Aguarda o tempo do ciclo (1 minuto)
            # Usamos um loop com sleep pequeno para permitir interrupção via KeyboardInterrupt se necessário
            while (time.time() - t_start) < DURACAO_MINUTO:
                time.sleep(0.1)
            
            # 3. Leitura Final
            t_end = time.time()
            e_end_uj = read_energy_uj(rapl_file)
            
            # 4. Cálculos
            delta_time = t_end - t_start
            delta_energy_uj = e_end_uj - e_start_uj
            
            # Evitar valores negativos em caso de reset do contador (raro em 60s, mas possível)
            if delta_energy_uj < 0:
                print("Aviso: Contador de energia resetou (overflow). Ignorando ciclo.")
                continue

            # Conversão de Unidades:
            # RAPL entrega microJoules (uJ)
            # 1 Joule = 1.000.000 uJ
            # 1 mWh = 3.6 Joules
            energy_joules = delta_energy_uj / 1_000_000.0
            energy_mwh = energy_joules / 3.6
            
            # Potência Média (mW)
            # Pode ser calculado como (Energia em mWh / Tempo em horas) 
            # ou (Energia em Joules / Tempo em segundos * 1000)
            tempo_horas = delta_time / 3600.0
            potencia_media_mw = energy_mwh / tempo_horas

            # 5. Salvar no CSV
            timestamp_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(ARQUIVO_SAIDA, 'a', newline='') as f:
                writer = csv.writer(f)
                # Formatação idêntica ao tvbox.py
                writer.writerow([
                    timestamp_agora, 
                    ciclo, 
                    f"{energy_mwh:.6f}", 
                    f"{potencia_media_mw:.2f}"
                ])

            print(f"Ciclo {ciclo} finalizado.")
            print(f"  > Energia Consumida: {energy_mwh:.4f} mWh")
            print(f"  > Potência Média:    {potencia_media_mw:.2f} mW")

    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    except PermissionError:
        print("\nERRO DE PERMISSÃO: Execute com 'sudo'. O RAPL exige acesso root.")
    except Exception as e:
        print(f"\nErro inesperado: {e}")

    print("\nMonitoramento finalizado.")

if __name__ == "__main__":
    monitorar_rapl()
