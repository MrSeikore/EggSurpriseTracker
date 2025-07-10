# Egg Surprise Inventory Tracker

Программа для отслеживания инвентаря в игре Egg Surprise.

## 📥 Как установить
1. **Для обычных пользователей** (просто скачать и запустить):
   - Перейди в раздел [Releases](https://github.com/MrSeikore/EggSurpriseTracker/releases)
   - Скачай файл `InventoryTracker.exe` (под Windows)
   - Запусти его!

2. **Для разработчиков** (если хочешь запустить код):
   - Установи [Python](https://www.python.org/downloads/)
   - Скачай файлы из репозитория
   - Открой терминал и введи:
     ```bash
     pip install -r requirements.txt
     python egg_final.py
     ```

## 🔧 Как собрать exe-файл самому
Если хочешь пересобрать программу:
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico --name=InventoryTracker egg_final.py
```

## 📞 Поддержка
Если есть вопросы — пиши мне в Discord: @mrseikore
