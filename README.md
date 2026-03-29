# Multiplayer Football Manager Game ⚽🏆

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![Pygame](https://img.shields.io/badge/pygame--ce-2.5.3-green)
![SQLAlchemy](https://img.shields.io/badge/sqlalchemy-2.0.40-red)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**A comprehensive, multiplayer Football Manager simulator built entirely in Python.** 

This repository contains my **BSc Thesis Project**. It demonstrates a robust client-server architecture, database management, real-time networking, and complex game logic encompassing player stats, match simulation, and club management. It is designed to be easily extensible and highly performant.

---

## 🌟 Key Features

### 🎮 Client (User Interface & Experience)
- **Robust GUI:** Designed meticulously using `pygame-ce` featuring a multi-screen management system.
- **Squad Management:** Intuitive drag-and-drop or click-based interfaces to manage your starting XI and substitutes.
- **Tactical Depth:** Set team formations (e.g., 4-4-2, 4-3-3), play styles, and individual player roles.
- **Live Transfer Market:** Real-time transfer system allowing managers to buy and sell players.
- **Match Simulation & Events:** Watch your team's tactical decisions unfold with live, simulated match events.
- **Multiplayer Capabilities:** Compete against other real players in localized or wide-area online tournaments.

### 🖥️ Server (Engine & Backend)
- **Real-Time TCP Server:** Multithreaded networking built entirely from scratch utilizing Python's `socket` library.
- **Complex Match Engine:** A sophisticated match simulator (`match_simulator.py`) using statistical algorithms (powered by Pandas/NumPy) to determine match events based on player attributes and chosen tactics.
- **Database Driven:** Heavy data lifting handled by `SQLAlchemy` ORM, enabling persistence of users, clubs, players, leagues, and transfer listings.
- **Data Initialization:** Seeds the simulation environment automatically using real-world-like datasets (`male_players.csv`).
- **Cron-like Scheduler:** Asynchronous handling of matchdays, training improvements, and season progressions.

---

## 📂 Project Structure

A clean, modular structure separating the presentation layer from the game engine and networking backend.

```text
Football_Manager_Game/
├── assets/                 # Graphics, fonts, and UI elements used by Pygame.
├── data/                   # Contains initial datasets (e.g., male_players.csv) to populate the database.
├── source/
│   ├── client/             # The Frontend / Game Client
│   │   ├── client_main.py  # The main entrypoint for launching the game client.
│   │   ├── game.py         # State machine managing the core game loop and rendering.
│   │   ├── network_client.py # Handles TCP connections/payloads to the server.
│   │   ├── ui_elements.py  # Custom Pygame UI components (text boxes, drop-downs, etc).
│   │   └── screens/        # Separate modules for each view feature:
│   │       ├── main_menu_screen.py, login_screen.py, squad_screen.py...
│   │       └── tactics_screen.py, transfers_screen.py, match_detail_screen.py...
│   ├── server/             # The Backend / Game Engine
│   │   ├── main_server.py  # The main entrypoint that launches the TCP/IP listening server.
│   │   ├── scheduler.py    # Background task runner for automated match simulations.
│   │   ├── database/       # SQLAlchemy models and SQLite/PostgreSQL connections.
│   │   │   ├── data_manager.py # Ingestion pipeline for CSV data -> Database.
│   │   │   └── models.py   # Database schemas (User, TournamentClub, TournamentPlayer).
│   │   └── simulation/     # The Math & Logic Engine
│   │       └── match_simulator.py # Advanced algorithms evaluating team strengths to derive results.
│   └── common/             # Shared logic between Client and Server (Constants, Enums).
└── requirements.txt        # Python dependency manifest.
```

---

## 🛠️ Technology Stack

- **Language:** Python 3.10+
- **Frontend / Graphics:** Pygame-CE (Community Edition)
- **Networking:** Python `socket` & `threading` (TCP/IPv4, JSON payloads)
- **Database / ORM:** SQLAlchemy (SQLite default, scalable to PostgreSQL/MySQL)
- **Data Processing:** Pandas & NumPy (used for rapid dataset parsing and math-heavy match simulations)
- **Packaging:** PyInstaller

---

## 🚀 Getting Started

To run the game, you will need to start the Game Server first, followed by launching one or more Game Clients.

### 1. Prerequisites
Ensure you have Python 3.10+ installed.
```bash
# Clone the repository
git clone https://github.com/yourusername/Football_Manager_Game.git
cd Football_Manager_Game

# Install the required dependencies
pip install -r requirements.txt
```

### 2. Starting the Server
The server will initialize the database on its first run and begin listening for client connections.
```bash
# From the root directory (Football_Manager_Game)
python source/server/main_server.py
```

### 3. Starting the Client
Once the server is running on `127.0.0.1:65432`, you can launch a client instance:
```bash
# Open a new terminal from the root directory
python source/client/client_main.py
```

---

## 🧠 Future Enhancements (Roadmap)
- Expanded Transfer Logic (AI Bidding).
- More detailed graphical match engine (2D radar view).
- Youth Academy integration to generate new regens.
- Implementation of Financial Fair Play rules and club budgets.