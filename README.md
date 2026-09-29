# Adaptive Serverless Execution Across the Computing Continuum

This repository contains the source code for an adaptive Function-as-a-Service (FaaS) orchestration system. The architecture dynamically distributes computational workloads across the Computing Continuum (Edge, Fog, and Cloud layers) to optimize execution time and minimize energy consumption on resource-constrained IoT devices. 

This project was developed as part of an undergraduate thesis in Computer Science at the State University of Western Paraná (UNIOESTE) and evaluates the use of repurposed TV Boxes as viable edge computing nodes.

## Features
* **Dynamic Workload Routing:** Automatically routes FaaS requests based on real-time hardware metrics (CPU and RAM).
* **Continuum Orchestration:** Seamlessly integrates Edge (Faasd), Fog (OpenFaaS), and Cloud layers.
* **Energy Optimization:** Prevents edge resource saturation, significantly reducing the energy footprint of IoT nodes.
* **Transparent Execution:** Client module abstracts the routing and offloading complexity from the end user.

## Repository Structure

* `adapt_exec_server.py`: The **Arbiter** component. A Flask-based server that monitors node metrics via Prometheus and decides the optimal execution host based on predefined thresholds.
* `adapt_exec_client.py`: The **Client** module. Interfaces with the Arbiter to retrieve the best host and transparently forwards the FaaS execution request.
* `config.yml`: Configuration file containing host URLs, function endpoints, and hardware utilization thresholds (CPU/RAM limits and cooldown intervals).
* `tests/`: Contains the evaluation scripts (`adaptive_test.py` and `static_test.py`) used to benchmark the architecture using YOLO object detection models.
* `power monitoring/`: Scripts and services used to measure baseline and active energy consumption across the Edge (via INA219 sensor) and Fog (via Intel RAPL) nodes.

## Prerequisites

To run this architecture, your infrastructure must have:
1. Python 3.8+ installed.
2. **FaaS Frameworks:** OpenFaaS deployed on Fog/Cloud nodes and Faasd deployed on Edge nodes.
3. **Monitoring:** Prometheus and Node Exporter installed and running on the Edge and Fog nodes to expose hardware metrics.
4. Required Python libraries: `requests`, `flask`, `pyyaml`.

## Usage

1. **Configure the Environment:**
   Edit the `config.yml` file to include your specific FaaS endpoints, Prometheus API URLs, and desired threshold limits for each node.

2. **Start the Arbiter (Server):**
   Run the orchestration server on a dedicated node (or lightweight edge device):
   
```bash
   python adapt_exec_server.py
```

3. **Run the Client Application:**
   Import the client module into your application, initialize it with your `config.yml`, and send requests:
   
```python
   from adapt_exec_client import adapt_exec_client

   client = adapt_exec_client("config.yml", arbiter_url="http://<ARBITER_IP>:<PORT>")
   client.send_config()

   # Example request
   response = client.request(function_name="yolo-inference", payload=image_data, format="bytes")
   print(response)
```

## Citation / Associated Publication
If you use this code in your research, please refer to our associated paper published in the *Journal of the Brazilian Computer Society (JBCS)*:
> Czerniej, R., & Oyamada, M. (2026). *Adaptive Execution of Serverless Functions Across the Computing Continuum*. Journal of the Brazilian Computer Society.
