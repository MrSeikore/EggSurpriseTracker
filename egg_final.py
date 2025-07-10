import requests
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict
import pytz
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
import pyperclip  # Для работы с буфером обмена

# Скрываем консоль при запуске через ярлык
if sys.executable.endswith("pythonw.exe"):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# Конфигурация
INVENTORY_API = "https://egg-surprise.shop/api/inventory/get"
ITEMS_API = "https://egg-surprise.shop/api/get-all-items"
CONFIG_FILE = "config.json"
CHECK_INTERVAL = 600  # 10 минут
HISTORY_FILE = "inventory_history.json"
TIMEZONE = pytz.timezone('Europe/Moscow')

class AuthWindow:
    def __init__(self, root, on_auth_success):
        self.root = root
        self.on_auth_success = on_auth_success
        self.setup_ui()
        
    def setup_ui(self):
        self.root.title("Egg Surprise - Авторизация")
        self.root.geometry("500x250")
        self.root.resizable(False, False)
        
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Введите токен авторизации:", font=('Arial', 12)).pack(pady=10)
        
        # Фрейм для поля ввода и кнопки вставки
        entry_frame = ttk.Frame(main_frame)
        entry_frame.pack(pady=5)
        
        self.token_entry = ttk.Entry(entry_frame, width=50)
        self.token_entry.pack(side=tk.LEFT, padx=5)
        self.token_entry.focus()
        
        paste_btn = ttk.Button(entry_frame, text="Вставить", command=self.paste_from_clipboard, width=8)
        paste_btn.pack(side=tk.LEFT)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Войти", command=self.authenticate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Выйти", command=self.root.quit).pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(main_frame, text="", foreground="red")
        self.status_label.pack()
        
        # Привязываем Enter к авторизации
        self.root.bind('<Return>', lambda e: self.authenticate())
    
    def paste_from_clipboard(self):
        try:
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                self.token_entry.delete(0, tk.END)
                self.token_entry.insert(0, clipboard_content)
        except Exception as e:
            self.status_label.config(text=f"Ошибка доступа к буферу обмена: {str(e)}")
    
    def authenticate(self):
        token = self.token_entry.get().strip()
        if not token:
            self.status_label.config(text="Токен не может быть пустым")
            return
            
        self.status_label.config(text="Проверка токена...")
        self.root.update()
        
        # Проверяем токен
        if self.check_token(token):
            self.save_token(token)
            self.on_auth_success(token)
            self.root.destroy()
        else:
            self.status_label.config(text="Неверный токен. Попробуйте снова.")
    
    def check_token(self, token):
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.get(INVENTORY_API, headers=headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def save_token(self, token):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"token": token}, f)
        except Exception as e:
            print(f"Ошибка сохранения токена: {e}")

class InventoryTracker:
    def __init__(self, root, token):
        self.root = root
        self.token = token
        self.history = {}
        self.current_inventory = None
        self.items_info = {}
        self.tracking_active = False
        self.tracking_thread = None
        self.show_changed_only = False
        self.sort_column = "current"
        self.sort_reverse = False
        self.search_query = tk.StringVar()
        self.selected_date = tk.StringVar(value=self.get_current_date_key())
        
        self.setup_ui()  # Сначала создаем интерфейс
        self.load_history()
        self.load_items_info()
        
        if not self.history:
            self.status("Первоначальная история не найдена. Загружаю текущий инвентарь...")
            self.initialize_first_run()
        else:
            self.update_inventory_display()

    def get_current_date_key(self):
        """Возвращает текущую дату в формате YYYY-MM-DD"""
        return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    def setup_ui(self):
        self.root.title("Egg Surprise - Трекер инвентаря")
        self.root.geometry("1200x700")
        self.root.configure(bg='#f0f0f0')
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Стили
        style = ttk.Style()
        style.theme_use('clam')
        
        # Основные стили
        style.configure('.', background='#f0f0f0', foreground='#333333', font=('Segoe UI', 10))
        style.configure('TButton', background='#4a6fa5', foreground='white', borderwidth=1,
                       relief='solid', font=('Segoe UI', 10, 'bold'), padding=8)
        style.map('TButton', background=[('active', '#3a5a8f'), ('disabled', '#cccccc')],
                foreground=[('disabled', '#888888')])
        style.configure('Active.TButton', background='#2c4d7f', foreground='white',
                      borderwidth=1, relief='solid', font=('Segoe UI', 10, 'bold'))
        style.configure('TFrame', background='#f0f0f0')
        style.configure('Header.TFrame', background='#2c4d7f')
        style.configure('Header.TLabel', background='#2c4d7f', foreground='white',
                       font=('Segoe UI', 12, 'bold'))
        style.configure('Treeview', background='white', foreground='#333333',
                      fieldbackground='white', borderwidth=1, font=('Segoe UI', 10),
                      rowheight=30)
        style.map('Treeview', background=[('selected', '#4a6fa5')], foreground=[('selected', 'white')])
        style.configure('Treeview.Heading', background='#2c4d7f', foreground='white',
                      font=('Segoe UI', 10, 'bold'), borderwidth=1, padding=5)

        # Главный контейнер
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Шапка приложения
        header_frame = ttk.Frame(main_frame, style='Header.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10), ipady=10)

        # Логотип и название
        title_frame = ttk.Frame(header_frame, style='Header.TFrame')
        title_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(title_frame, text="Egg Surprise", style='Header.TLabel', 
                font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="Трекер инвентаря", style='Header.TLabel').pack(side=tk.LEFT, padx=(5,0))

        # Панель инструментов
        tool_frame = ttk.Frame(header_frame, style='Header.TFrame')
        tool_frame.pack(side=tk.RIGHT, padx=10)

        # Кнопки
        self.refresh_btn = ttk.Button(tool_frame, text="🔄 Обновить", 
                                    command=self.refresh_data, style='TButton')
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.track_btn = ttk.Button(tool_frame, text="🔍 Начать отслеживание", 
                                  command=self.toggle_tracking, style='TButton')
        self.track_btn.pack(side=tk.LEFT, padx=5)
        
        export_btn = ttk.Button(tool_frame, text="📤 Экспорт данных", 
                              command=self.export_data, style='TButton')
        export_btn.pack(side=tk.LEFT, padx=5)
        
        self.filter_btn = ttk.Button(tool_frame, text="👁️ Показать все", 
                              command=self.toggle_filter, style='TButton')
        self.filter_btn.pack(side=tk.LEFT, padx=5)
        
        logout_btn = ttk.Button(tool_frame, text="🔄 Сменить аккаунт", 
                              command=self.logout, style='TButton')
        logout_btn.pack(side=tk.LEFT, padx=5)

        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)

        # Выбор даты
        date_frame = ttk.Frame(control_frame)
        date_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(date_frame, text="📅 Дата:").pack(side=tk.LEFT)
        
        prev_day_btn = ttk.Button(date_frame, text="◀", command=self.prev_day, width=3)
        prev_day_btn.pack(side=tk.LEFT, padx=2)
        
        self.date_combo = ttk.Combobox(date_frame, textvariable=self.selected_date, state="readonly")
        self.date_combo.pack(side=tk.LEFT, padx=2)
        self.update_date_combobox()
        self.date_combo.bind("<<ComboboxSelected>>", self.on_date_selected)
        
        next_day_btn = ttk.Button(date_frame, text="▶", command=self.next_day, width=3)
        next_day_btn.pack(side=tk.LEFT, padx=2)

        # Поиск
        search_frame = ttk.Frame(control_frame)
        search_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(search_frame, text="🔍 Поиск:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_query, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.update_inventory_display())

        # Сортировка
        sort_frame = ttk.Frame(control_frame)
        sort_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Label(sort_frame, text="Сортировка:").pack(side=tk.LEFT)
        self.sort_combo = ttk.Combobox(sort_frame, 
                                     values=["Название", "ID", "Количество", "Изменение"], 
                                     state="readonly")
        self.sort_combo.pack(side=tk.LEFT, padx=5)
        self.sort_combo.set("Количество")
        self.sort_combo.bind("<<ComboboxSelected>>", self.change_sort)

        # Таблица с данными
        self.tree_frame = ttk.Frame(main_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(self.tree_frame, 
                               columns=("id", "name_ru", "name_en", "initial", "current", "change"), 
                               show="headings")
        
        # Настройка колонок
        self.tree.heading("id", text="ID", command=lambda: self.sort_by_column("id"))
        self.tree.column("id", width=80, anchor=tk.CENTER)
        
        self.tree.heading("name_ru", text="Название (RU)", command=lambda: self.sort_by_column("name_ru"))
        self.tree.column("name_ru", width=250, anchor=tk.W)
        
        self.tree.heading("name_en", text="Название (EN)", command=lambda: self.sort_by_column("name_en"))
        self.tree.column("name_en", width=250, anchor=tk.W)
        
        self.tree.heading("initial", text="Начало дня", command=lambda: self.sort_by_column("initial"))
        self.tree.column("initial", width=100, anchor=tk.CENTER)
        
        self.tree.heading("current", text="Текущее", command=lambda: self.sort_by_column("current"))
        self.tree.column("current", width=100, anchor=tk.CENTER)
        
        self.tree.heading("change", text="Изменение", command=lambda: self.sort_by_column("change"))
        self.tree.column("change", width=100, anchor=tk.CENTER)
        
        # Цвета строк
        self.tree.tag_configure('evenrow', background='#f8f8f8')
        self.tree.tag_configure('oddrow', background='#ffffff')
        self.tree.tag_configure('positive', foreground='green')
        self.tree.tag_configure('negative', foreground='red')
        
        # Полоса прокрутки
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Статус бар
        self.status_var = tk.StringVar()
        status_bar = ttk.Frame(main_frame)
        status_bar.pack(fill=tk.X, pady=(5,0))
        ttk.Label(status_bar, textvariable=self.status_var, 
                 background='#2c4d7f', foreground='white',
                 anchor=tk.W, padding=5).pack(fill=tk.X)

    def on_close(self):
        """Обработчик закрытия окна"""
        self.stop_tracking()
        self.root.destroy()

    def logout(self):
        """Выход из аккаунта"""
        self.stop_tracking()
        if os.path.exists(CONFIG_FILE):
            try:
                os.remove(CONFIG_FILE)
            except Exception as e:
                print(f"Ошибка удаления файла конфигурации: {e}")
        self.root.destroy()
        # Перезапускаем приложение
        main()

    def update_date_combobox(self):
        dates = sorted(self.history.keys(), reverse=True)
        if dates:
            self.date_combo['values'] = dates
            if not self.selected_date.get() in dates:
                self.selected_date.set(dates[0])
        else:
            self.date_combo['values'] = [self.get_current_date_key()]
            self.selected_date.set(self.get_current_date_key())

    def on_date_selected(self, event=None):
        self.update_inventory_display()

    def prev_day(self):
        dates = sorted(self.history.keys())
        current_idx = dates.index(self.selected_date.get()) if self.selected_date.get() in dates else -1
        if current_idx > 0:
            self.selected_date.set(dates[current_idx - 1])
            self.update_inventory_display()

    def next_day(self):
        dates = sorted(self.history.keys())
        current_idx = dates.index(self.selected_date.get()) if self.selected_date.get() in dates else -1
        if current_idx < len(dates) - 1:
            self.selected_date.set(dates[current_idx + 1])
            self.update_inventory_display()

    def change_sort(self, event):
        sort_options = {
            "Название": "name_ru",
            "ID": "id",
            "Количество": "current",
            "Изменение": "change"
        }
        self.sort_column = sort_options.get(self.sort_combo.get(), "current")
        self.update_inventory_display()

    def sort_by_column(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.update_inventory_display()

    def toggle_filter(self):
        self.show_changed_only = not self.show_changed_only
        if self.show_changed_only:
            self.filter_btn.config(text="👁️ Показать все")
            self.status("Показаны только измененные предметы")
        else:
            self.filter_btn.config(text="👁️ Только изменения")
            self.status("Показаны все предметы")
        self.update_inventory_display()

    def status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

    def debug_print(self, message, data=None):
        print(f"[DEBUG] {message}")

    def load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                self.debug_print("История загружена из файла")
            else:
                self.history = {}
                self.debug_print("Файл истории не найден, создана новая история")
        except Exception as e:
            print(f"Ошибка при загрузке истории: {e}")
            self.history = {}

    def save_history(self):
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            self.debug_print("История сохранена в файл")
        except Exception as e:
            print(f"Ошибка при сохранении истории: {e}")

    def make_api_request(self, url):
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ошибка при запросе к {url}: {e}")
            return None

    def fetch_inventory(self):
        data = self.make_api_request(INVENTORY_API)
        if data is None:
            self.status("Не удалось получить инвентарь")
            return None
        
        if isinstance(data, dict) and 'response' in data:
            return data['response']
        return data

    def load_items_info(self):
        data = self.make_api_request(ITEMS_API)
        if data and isinstance(data, list):
            self.debug_print(f"Получено {len(data)} предметов из API")
            for item in data:
                item_id = str(item.get('Itemdefid', ''))
                if item_id:
                    self.items_info[item_id] = item
            self.status(f"Загружена информация о {len(self.items_info)} предметах")
        else:
            self.status("Не удалось загрузить информацию о предметах")

    def get_item_info(self, item_id):
        item_id_str = str(item_id)
        if item_id_str in self.items_info:
            return self.items_info[item_id_str]
        return {
            "Name": f"Unknown (ID {item_id})",
            "NameRu": f"Неизвестно (ID {item_id})",
            "Itemdefid": item_id
        }

    def process_inventory(self, inventory_data):
        if inventory_data is None:
            self.status("Ошибка: inventory_data is None")
            return None

        if not isinstance(inventory_data, list):
            self.status(f"Ошибка: inventory_data должен быть list, получен {type(inventory_data)}")
            return None

        inventory = defaultdict(int)
        for item in inventory_data:
            if not isinstance(item, dict):
                print(f"Пропущен невалидный предмет: {item}")
                continue
                
            item_id = str(item.get('TypeId', ''))
            if not item_id:
                print(f"Пропущен предмет без TypeId: {item}")
                continue
            
            count = item.get('Count', 1)
            inventory[item_id] += count

        return dict(inventory)

    def initialize_day(self, date_key):
        if date_key not in self.history:
            self.history[date_key] = {
                "initial": self.current_inventory.copy(),
                "changes": [],
                "last_state": self.current_inventory.copy()
            }
            self.save_history()
            self.update_date_combobox()

    def initialize_first_run(self):
        self.status("Инициализация первого запуска...")
        inventory_data = self.fetch_inventory()
        
        if inventory_data is not None:
            self.current_inventory = self.process_inventory(inventory_data)
            if self.current_inventory:
                date_key = self.get_current_date_key()
                self.history[date_key] = {
                    "initial": self.current_inventory.copy(),
                    "changes": [],
                    "last_state": self.current_inventory.copy()
                }
                self.save_history()
                self.update_date_combobox()
                self.status("Первоначальный инвентарь успешно сохранен!")
                self.update_inventory_display()
            else:
                self.status("Не удалось обработать данные инвентаря")
        else:
            self.status("Не удалось загрузить инвентарь. Проверьте токен и подключение к интернету.")

    def track_changes(self):
        date_key = self.get_current_date_key()
        
        if not self.current_inventory:
            self.status("Ошибка: current_inventory не загружен")
            return

        self.initialize_day(date_key)

        last_state = self.history[date_key]["last_state"]
        changes = {}

        all_item_ids = set(last_state.keys()).union(set(self.current_inventory.keys()))
        
        for item_id in all_item_ids:
            old_count = last_state.get(item_id, 0)
            new_count = self.current_inventory.get(item_id, 0)
            
            if old_count != new_count:
                changes[item_id] = new_count - old_count

        if changes:
            change_record = {
                "timestamp": datetime.now(TIMEZONE).isoformat(),
                "changes": changes
            }
            self.history[date_key]["changes"].append(change_record)
            self.history[date_key]["last_state"] = self.current_inventory.copy()
            self.save_history()
            
            change_messages = []
            for item_id, delta in changes.items():
                item_info = self.get_item_info(item_id)
                name = item_info.get('NameRu', item_info.get('Name', f'ID {item_id}'))
                initial_count = self.history[date_key]["initial"].get(item_id, 0)
                current_count = self.current_inventory.get(item_id, 0)
                
                change_messages.append(
                    f"- {name}: {delta:+d} (было: {initial_count}, сейчас: {current_count})"
                )
            
            self.status(f"Обнаружены изменения в инвентаре:\n" + "\n".join(change_messages))
            self.update_inventory_display()
        else:
            self.status("Изменений не обнаружено")

    def update_inventory_display(self):
        if not self.current_inventory:
            return
            
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        search_term = self.search_query.get().lower()
        date_key = self.selected_date.get()
        
        if date_key not in self.history:
            self.status(f"Нет данных за {date_key}")
            return
            
        initial_inventory = self.history[date_key]["initial"]
        current_inventory = self.history[date_key]["last_state"]
        
        items_data = []
        for item_id, current_count in current_inventory.items():
            item_info = self.get_item_info(item_id)
            name_ru = item_info.get('NameRu', '')
            name_en = item_info.get('Name', '')
            
            if search_term and search_term not in name_ru.lower() and search_term not in name_en.lower() and search_term not in item_id.lower():
                continue
                
            initial_count = initial_inventory.get(item_id, 0)
            change = current_count - initial_count
                
            if self.show_changed_only and change == 0:
                continue
                
            items_data.append({
                "id": item_id,
                "name_ru": name_ru,
                "name_en": name_en,
                "initial": initial_count,
                "current": current_count,
                "change": change
            })
        
        reverse_sort = self.sort_reverse
        
        if self.sort_column == "change":
            if reverse_sort:
                items_data.sort(key=lambda x: (-x["change"] if x["change"] > 0 else float('inf') - x["change"]))
            else:
                items_data.sort(key=lambda x: (x["change"] if x["change"] < 0 else float('inf') + x["change"]))
        else:
            items_data.sort(key=lambda x: x[self.sort_column], reverse=reverse_sort)
        
        for idx, item in enumerate(items_data):
            values = (
                item["id"],
                item["name_ru"],
                item["name_en"],
                item["initial"],
                item["current"],
                f"{item['change']:+d}" if item["change"] != 0 else ""
            )
            
            tags = ('evenrow',) if idx % 2 == 0 else ('oddrow',)
            if item["change"] > 0:
                tags += ('positive',)
            elif item["change"] < 0:
                tags += ('negative',)
            
            try:
                self.tree.insert("", tk.END, values=values, tags=tags)
            except Exception as e:
                print(f"Ошибка при добавлении предмета в таблицу: {e}")

    def refresh_data(self):
        self.status("Обновление данных...")
        
        inventory_data = self.fetch_inventory()
        if inventory_data is not None:
            processed = self.process_inventory(inventory_data)
            if processed is not None:
                self.current_inventory = processed
                self.track_changes()
                self.status("Данные успешно обновлены")
            else:
                self.status("Не удалось обработать данные инвентаря")
        else:
            self.status("Не удалось получить данные инвентаря")
        
        self.load_items_info()
        self.update_inventory_display()

    def toggle_tracking(self):
        if self.tracking_active:
            self.stop_tracking()
        else:
            self.start_tracking()

    def start_tracking(self):
        if self.tracking_active:
            return
            
        self.tracking_active = True
        self.track_btn.config(text="⏹️ Стоп отслеживания")
        self.status("Автоматическое отслеживание запущено")
        
        self.tracking_thread = threading.Thread(target=self.tracking_loop, daemon=True)
        self.tracking_thread.start()

    def stop_tracking(self):
        self.tracking_active = False
        self.track_btn.config(text="🔍 Начать отслеживание")
        self.status("Автоматическое отслеживание остановлено")

    def tracking_loop(self):
        while self.tracking_active:
            self.refresh_data()
            
            for _ in range(CHECK_INTERVAL):
                if not self.tracking_active:
                    break
                time.sleep(1)

    def export_data(self):
        try:
            export_file = "inventory_export_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
            with open(export_file, 'w', encoding='utf-8') as f:
                f.write("ID;Название (RU);Название (EN);Начало дня;Текущее;Изменение\n")
                
                for item in self.tree.get_children():
                    values = self.tree.item(item, 'values')
                    f.write(";".join(values) + "\n")
                    
            self.status(f"Данные экспортированы в {export_file}")
            messagebox.showinfo("Экспорт завершен", f"Данные успешно экспортированы в файл:\n{export_file}")
        except Exception as e:
            self.status(f"Ошибка экспорта: {str(e)}")
            messagebox.showerror("Ошибка экспорта", f"Не удалось экспортировать данные:\n{str(e)}")

    def run(self):
        self.root.mainloop()

def load_saved_token():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('token')
        except Exception:
            return None
    return None

def main():
    # Проверяем сохраненный токен
    saved_token = load_saved_token()
    
    if saved_token:
        # Проверяем токен
        auth_root = tk.Tk()
        auth_window = AuthWindow(auth_root, lambda token: None)
        if auth_window.check_token(saved_token):
            auth_root.destroy()
            # Токен валидный, запускаем основное приложение
            root = tk.Tk()
            app = InventoryTracker(root, saved_token)
            app.run()
            return
    
    # Если токена нет или он невалидный, показываем окно авторизации
    auth_root = tk.Tk()
    auth_window = AuthWindow(auth_root, lambda token: start_main_app(auth_root, token))
    auth_root.mainloop()

def start_main_app(auth_root, token):
    auth_root.destroy()
    root = tk.Tk()
    app = InventoryTracker(root, token)
    app.run()

if __name__ == "__main__":
    try:
        import pyperclip
    except ImportError:
        print("Установите модуль pyperclip для работы с буфером обмена: pip install pyperclip")
        sys.exit(1)
    
    main()