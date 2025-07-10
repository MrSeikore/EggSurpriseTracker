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


## 🔧 Как получить Токен 
   - Зайти на любую страницу egg-surprise.shop
   - Нажать F12 или ПКМ -> Посмотреть код и нажать F5
   -Открыть вкладку NETWORK
<img width="583" height="298" alt="image" src="https://github.com/user-attachments/assets/61e971ee-1983-4f79-b9fe-84bced1082f7" />
   
   -Выбрать любое из обращение к API и в HEADERS будет поле authorization где нужно скопировать все, что под Bearer 
<img width="1417" height="940" alt="image" src="https://github.com/user-attachments/assets/c88700e3-cc93-46ea-9932-b40bf13013c8" />
