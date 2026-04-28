import tkinter as tk
from tkinter import ttk, messagebox
from pymongo import MongoClient


try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    client.admin.command('ping')  # Тест на връзката
    db = client["nutrition_db"]
    db["foods"].create_index("name", unique=True)
    db["daily_log"].create_index("date")
except Exception as e:
    # Ако базата не работи, показваме съобщение и спираме програмата
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Грешка с Базата", f"Моля, стартирайте MongoDB!\n\nДетайли: {e}")
    exit()


def add_food():
    name = entry_add_name.get().strip().lower()
    if not name:
        messagebox.showwarning("Внимание", "Въведете име на храната!")
        return

    try:
        cal = float(entry_add_cal.get())
        pro = float(entry_add_pro.get())
        carb = float(entry_add_carb.get())
        fat = float(entry_add_fat.get())

        if db["foods"].find_one({"name": name}):
            messagebox.showerror("Грешка", f"Храната '{name.capitalize()}' вече съществува!")
            return

        db["foods"].insert_one({"name": name, "calories": cal, "protein": pro, "carbs": carb, "fats": fat})
        messagebox.showinfo("Успех", f"Успешно добавихте '{name.capitalize()}'!")

        # Изчистване на полетата след успех
        for entry in [entry_add_name, entry_add_cal, entry_add_pro, entry_add_carb, entry_add_fat]:
            entry.delete(0, tk.END)

    except ValueError:
        messagebox.showerror("Грешка", "Моля, въведете валидни числа за макросите (използвайте точка)!")


def delete_food():
    name = entry_del_name.get().strip().lower()
    if not name:
        return

    result = db["foods"].delete_one({"name": name})
    if result.deleted_count > 0:
        messagebox.showinfo("Успех", f"Храната '{name.capitalize()}' беше изтрита.")
        entry_del_name.delete(0, tk.END)
    else:
        messagebox.showwarning("Внимание", f"Не бе намерена храна с име '{name.capitalize()}'.")


def log_food():
    date = entry_log_date.get().strip()
    food_name = entry_log_name.get().strip().lower()

    if not date or not food_name:
        messagebox.showwarning("Внимание", "Попълнете дата и име на храна!")
        return

    food = db["foods"].find_one({"name": food_name})
    if not food:
        messagebox.showerror("Грешка", "Тази храна не е в каталога! Добавете я първо от таб 'Каталог'.")
        return

    try:
        grams = float(entry_log_grams.get())
        multiplier = grams / 100

        log_doc = {
            "date": date,
            "food_name": food_name,
            "grams": grams,
            "macros": {
                "calories": food["calories"] * multiplier,
                "protein": food["protein"] * multiplier,
                "carbs": food["carbs"] * multiplier,
                "fats": food["fats"] * multiplier
            }
        }
        db["daily_log"].insert_one(log_doc)
        messagebox.showinfo("Успех", f"Записахте {grams}g {food_name.capitalize()} за дата {date}!")
        entry_log_name.delete(0, tk.END)
        entry_log_grams.delete(0, tk.END)

    except ValueError:
        messagebox.showerror("Грешка", "Моля, въведете валидно число за грамаж!")


def analyze_macros():
    date = entry_analyze_date.get().strip()

    try:
        goal = float(entry_analyze_goal.get())
    except ValueError:
        messagebox.showerror("Грешка", "Въведете валидно число за дневна цел!")
        return

    # Агрегация (Aggregation Pipeline)
    pipeline = [
        {"$match": {"date": date}},
        {"$group": {
            "_id": "$date",
            "total_calories": {"$sum": "$macros.calories"},
            "total_protein": {"$sum": "$macros.protein"},
            "total_carbs": {"$sum": "$macros.carbs"},
            "total_fats": {"$sum": "$macros.fats"},
            "consumed": {"$push": {"n": "$food_name", "g": "$grams"}}
        }}
    ]

    result = list(db["daily_log"].aggregate(pipeline))

    # Показване на резултатите в текстовото поле
    text_analyze_result.config(state="normal")  # Разрешаваме писането
    text_analyze_result.delete(1.0, tk.END)  # Изчистваме стария текст

    if result:
        res = result[0]
        text_analyze_result.insert(tk.END, f"=== КОНСУМИРАНО НА {date} ===\n")
        for f in res["consumed"]:
            text_analyze_result.insert(tk.END, f" - {f['n'].capitalize()}: {f['g']}g\n")

        total_cal = res['total_calories']
        text_analyze_result.insert(tk.END, f"\n=== ОБЩО МАКРОСИ ===\n")
        text_analyze_result.insert(tk.END, f"Калории: {total_cal:.2f} kcal\n")
        text_analyze_result.insert(tk.END, f"Протеин: {res['total_protein']:.2f} g\n")
        text_analyze_result.insert(tk.END, f"Въглехидрати: {res['total_carbs']:.2f} g\n")
        text_analyze_result.insert(tk.END, f"Мазнини: {res['total_fats']:.2f} g\n")

        diff = goal - total_cal
        text_analyze_result.insert(tk.END, f"\n=== ДНЕВНА ЦЕЛ ({goal} kcal) ===\n")
        if diff >= 0:
            text_analyze_result.insert(tk.END, f"✅ Остават ви още {diff:.2f} kcal.\n")
        else:
            text_analyze_result.insert(tk.END, f"⚠️ Превишихте целта с {abs(diff):.2f} kcal!\n")
    else:
        text_analyze_result.insert(tk.END, f"Няма намерени записи за {date}.")

    text_analyze_result.config(state="disabled")  # Забраняваме ръчното писане от потребителя


def filter_foods():
    try:
        min_pro = float(entry_filter_pro.get())
        query = {"protein": {"$gte": min_pro}}
        results = db["foods"].find(query)

        text_filter_result.config(state="normal")
        text_filter_result.delete(1.0, tk.END)

        found = False
        text_filter_result.insert(tk.END, f"Храни с над {min_pro}g протеин:\n\n")
        for food in results:
            found = True
            text_filter_result.insert(tk.END, f" • {food['name'].capitalize()} ({food['protein']}g)\n")

        if not found:
            text_filter_result.insert(tk.END, "Няма намерени храни.")

        text_filter_result.config(state="disabled")
    except ValueError:
        messagebox.showerror("Грешка", "Въведете валидно число за протеин!")


root = tk.Tk()
root.title("Food Nutrition Logger")
root.geometry("450x500")
root.resizable(False, False)  # Фиксиран размер на прозореца

notebook = ttk.Notebook(root)
notebook.pack(pady=10, expand=True)

tab_catalog = ttk.Frame(notebook, width=400, height=450)
notebook.add(tab_catalog, text='Каталог')

ttk.Label(tab_catalog, text="ДОБАВЯНЕ НА ХРАНА", font=("Arial", 10, "bold")).pack(pady=10)
ttk.Label(tab_catalog, text="Име:").pack();
entry_add_name = ttk.Entry(tab_catalog);
entry_add_name.pack()
ttk.Label(tab_catalog, text="Калории (на 100g):").pack();
entry_add_cal = ttk.Entry(tab_catalog);
entry_add_cal.pack()
ttk.Label(tab_catalog, text="Протеин (на 100g):").pack();
entry_add_pro = ttk.Entry(tab_catalog);
entry_add_pro.pack()
ttk.Label(tab_catalog, text="Въглехидрати (на 100g):").pack();
entry_add_carb = ttk.Entry(tab_catalog);
entry_add_carb.pack()
ttk.Label(tab_catalog, text="Мазнини (на 100g):").pack();
entry_add_fat = ttk.Entry(tab_catalog);
entry_add_fat.pack()
tk.Button(tab_catalog, text="Добави в каталога", bg="#4CAF50", fg="white", command=add_food).pack(pady=10)

ttk.Separator(tab_catalog, orient='horizontal').pack(fill='x', pady=10)

ttk.Label(tab_catalog, text="ИЗТРИВАНЕ НА ХРАНА", font=("Arial", 10, "bold")).pack(pady=5)
ttk.Label(tab_catalog, text="Име:").pack();
entry_del_name = ttk.Entry(tab_catalog);
entry_del_name.pack()
tk.Button(tab_catalog, text="Изтрий", bg="#f44336", fg="white", command=delete_food).pack(pady=5)

tab_log = ttk.Frame(notebook, width=400, height=450)
notebook.add(tab_log, text='Запиши Хранене')

ttk.Label(tab_log, text="ЗАПИС НА ХРАНЕНЕ", font=("Arial", 10, "bold")).pack(pady=15)
ttk.Label(tab_log, text="Дата (ДД.ММ.ГГГГ):").pack();
entry_log_date = ttk.Entry(tab_log);
entry_log_date.pack(pady=5)
ttk.Label(tab_log, text="Име на храна:").pack();
entry_log_name = ttk.Entry(tab_log);
entry_log_name.pack(pady=5)
ttk.Label(tab_log, text="Грамаж (g):").pack();
entry_log_grams = ttk.Entry(tab_log);
entry_log_grams.pack(pady=5)

tk.Button(tab_log, text="Запиши в дневника", bg="#2196F3", fg="white", width=20, command=log_food).pack(pady=20)

tab_analyze = ttk.Frame(notebook, width=400, height=450)
notebook.add(tab_analyze, text='Дневен Анализ')

ttk.Label(tab_analyze, text="Дата (ДД.ММ.ГГГГ):").pack(pady=5);
entry_analyze_date = ttk.Entry(tab_analyze);
entry_analyze_date.pack()
ttk.Label(tab_analyze, text="Цел (Калории):").pack(pady=5);
entry_analyze_goal = ttk.Entry(tab_analyze);
entry_analyze_goal.pack()
tk.Button(tab_analyze, text="Анализирай (Aggregation)", bg="#FF9800", fg="white", command=analyze_macros).pack(pady=10)

text_analyze_result = tk.Text(tab_analyze, height=15, width=45, state="disabled", bg="#f0f0f0")
text_analyze_result.pack(pady=10)

tab_filter = ttk.Frame(notebook, width=400, height=450)
notebook.add(tab_filter, text='Филтър')

ttk.Label(tab_filter, text="ТЪРСЕНЕ ПО ПРОТЕИН", font=("Arial", 10, "bold")).pack(pady=15)
ttk.Label(tab_filter, text="Минимално количество (g):").pack();
entry_filter_pro = ttk.Entry(tab_filter);
entry_filter_pro.pack(pady=5)
tk.Button(tab_filter, text="Филтрирай", bg="#9C27B0", fg="white", command=filter_foods).pack(pady=10)

text_filter_result = tk.Text(tab_filter, height=15, width=45, state="disabled", bg="#f0f0f0")
text_filter_result.pack(pady=10)

root.mainloop()