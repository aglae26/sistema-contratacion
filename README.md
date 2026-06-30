# 📑 Sistema de Gestión Documental y Contratación Multi-Sociedad

Aplicación a medida diseñada para centralizar, automatizar y archivar contratos laborales, actas y memorandos para múltiples sociedades comerciales. El sistema opera bajo un enfoque híbrido de automatización web e integración con hardware biométrico y el software de nómina Doisol.

## 🚀 Arquitectura y Tecnologías
* **Frontend:** React.js (Preparado para integración WebHID/WebAssembly para Pad Wacom STU-430).
* **Backend:** Python (FastAPI) asíncrono.
* **Base de Datos:** PostgreSQL 15 (Estructura relacional Multi-Sociedad).
* **Infraestructura:** Todo el ecosistema se encuentra encapsulado y orquestado mediante **Docker** y **Docker Compose**.

## 📁 Estructura del Proyecto
* `/backend`: Código del servidor, API REST, conexión ORM (SQLAlchemy) y motor de PDF.
* `/frontend`: Interfaz de usuario en React.js.
* `docker-compose.yml`: Orquestador de contenedores de la solución.

## 🛠️ Requisitos Previos
Es necesario tener instalado en la máquina local:
1.  [Docker Desktop](https://www.docker.com/products/docker-desktop/) con soporte de virtualización activado.
2.  Un editor de código (IDE).

## 🏁 Instrucciones para Arranque Rápido
Para encender todo el entorno de desarrollo (Base de datos, Backend y Frontend) con un solo comando, abre una terminal en la raíz de este proyecto y ejecuta:

```bash
docker compose up --build