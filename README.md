# 🌐 Networked Industrial SCADA System (Python + OPC UA)

![Python](https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python)
![Protocol](https://img.shields.io/badge/Protocol-OPC%20UA-orange?style=for-the-badge)
![Architecture](https://img.shields.io/badge/Architecture-Client%20Server-green?style=for-the-badge)

## 📌 Project Overview
This project demonstrates a real-world industrial Client–Server SCADA architecture where a Python-based HMI communicates with a remote PLC through Kepware OPC UA over LAN.

The system is built across two separate physical machines to replicate an actual factory environment where the control room and machine network operate independently.

This is not a simulation-only UI — it performs real-time read/write communication with PLC logic through industrial protocols.

---

## 🏗 System Architecture

| Machine | IP Address | Role | Software |
|--------|-----------|------|---------|
| **PC 1 (Server)** | 192.168.0.20 | PLC + OPC UA Server | CODESYS SoftPLC + Kepware |
| **PC 2 (Client)** | 192.168.0.10 | SCADA/HMI | Python (PySide6) |

### Data Flow
Python HMI → OPC UA (TCP/IP) → Kepware → PLC  
PLC → Kepware → Python HMI (feedback)

Operator commands and setpoints are written to PLC via OPC UA, and live machine data is read back into the HMI for monitoring and visualization.

---

## 🧱 Logical System Architecture

```mermaid
graph TD
    PLC["PLC / Controller"] -->|"OPC UA / Modbus TCP"| OPC["Kepware OPC UA Server"]
    OPC -->|"TCP/IP"| HMI["Python HMI (PySide6)"]
    HMI -->|"Write Commands"| OPC
    HMI -->|"Read Live Data"| OPC
    HMI -->|"Log Production Data"| DB[("SQLite Database")]
    HMI -->|"Visualize"| UI["Operator Dashboard"]
    HMI -->|"Generate Reports"| RPT["PDF & Excel Reports"]
    DB -->|"Dataset for Future"| AI["AI / Analytics Layer"]
    HMI -->|"MQTT (Future)"| CLOUD["Cloud / Remote Monitoring"]
