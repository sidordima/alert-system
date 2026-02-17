import time
from datetime import datetime
import logging
from app.classes import Status, Compare, SSLcheck
from app.alert import send_tg_msg
import yaml
import httpx
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("service_check.log"),
        logging.StreamHandler()  # Это выведет логи в терминал
    ]
)


def read_config(config_file):
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Couldn't read config file:{e}")
    return config


def load_tasks(config):
    tasks = config['tasks']
    # convert task to dictionary
    # test 1
    for task in tasks:
        task['condition'] = []
        for cond in task['condition_true']:
            class_mame = next(iter(cond))
            match class_mame:
                case "Status":
                    task['condition'].append(Status(**cond['Status']))
                case "Compare":
                    task['condition'].append(Compare(**cond['Compare']))
                case "SSLcheck":
                    task['condition'].append(SSLcheck(**cond['SSLcheck']))

        del task['condition_true']
    return tasks


async def run_monitoring():
    config = read_config("config.yml")
    # !!! ОБЯЗАТЕЛЬНО ВЫЗЫВАЕМ ЗАГРУЗКУ ОБЪЕКТОВ !!!
    tasks_config = load_tasks(config)

    tg = config['telegram']
    # --- Блок логирования запуска ---
    start_msg = (
        f"\n{'=' * 40}\n"
        f"🚀 Monitoring System Started\n"
        f"⏰ Time: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"📊 Tasks loaded: {len(tasks_config)}\n"
        f"🆔 TG Chat ID: {tg['chat_id']}\n"
        f"{'=' * 40}"
    )
    print(start_msg)  # Вывод в консоль
    logging.info(start_msg)  # Запись в файл service_check.log

    next_check = {task["name"]: 0 for task in tasks_config}

    async with httpx.AsyncClient() as client:
        while True:
            now = time.time()
            coros_to_run = []
            task_indices = []
            prev_statuses = {}

            for idx, task in enumerate(tasks_config):
                if now >= next_check[task["name"]]:
                    # Запоминаем статус ДО проверки
                    prev_statuses[idx] = all([x.last_status for x in task['condition']])
                    # Формируем группу проверок для конкретной задачи
                    check_group = asyncio.gather(*[x.check(client) for x in task['condition']])
                    coros_to_run.append(check_group)
                    task_indices.append(idx)
                    next_check[task["name"]] = now + task["check_interval"]

            if coros_to_run:
                # Контрольный запрос
                control_coro = client.get("http://connectivitycheck.gstatic.com/generate_204", timeout=3.0)

                # Запускаем всё разом
                all_results = await asyncio.gather(*coros_to_run, control_coro, return_exceptions=True)

                control_res = all_results[-1]

                # Проверяем связь: если это Exception или статус ошибки (4xx, 5xx)
                if isinstance(control_res, Exception):
                    logging.warning(f"⚠️ Сеть монитора под вопросом (Control Check Error: {control_res})")
                    vps_is_reachable = False
                else:
                    vps_is_reachable = control_res.is_success

                if not vps_is_reachable:
                    logging.warning("Monitoring node network issue! Skipping alerts.")
                else:
                    for i, task_idx in enumerate(task_indices):
                        task_obj = tasks_config[task_idx]
                        # 1. Считаем текущий статус
                        current_group_results = all_results[i]
                        new_result = False if isinstance(current_group_results, Exception) else all(
                            current_group_results)

                        prev_result = prev_statuses[task_idx]
                        # 3. Если статус изменился на "Resolved" (True)
                        if prev_result is False and new_result is True:
                            # Ищем все остальные сервисы, которые СЕЙЧАС лежат
                            failed_services = [
                                t["name"] for t in tasks_config
                                if t["name"] != task_obj["name"] and (
                                            not all([c.last_status for c in t["condition"]]) or not all(
                                        [c.succ_check for c in t["condition"]]))
                            ]

                            # Формируем расширенное сообщение
                            status_text = f"{datetime.now():%Y-%m-%d %H:%M:%S} ✅ {task_obj['name']} Resolved!"
                            if failed_services:
                                status_text += f"\n\nStill down 🔴:\n- " + "\n- ".join(failed_services)
                            else:
                                status_text += "\n\nAll systems are green! 🟢"

                            send_tg_msg(status_text, tg['token'], tg['chat_id'])

                        # 4. Если статус изменился на "Alert" (False)
                        elif prev_result is True and new_result is False:
                            print("Должны послать мессагу!")
                            send_tg_msg(f"{datetime.now():%Y-%m-%d %H:%M:%S} ❗ {task_obj['name']} Alert!",
                                        tg['token'], tg['chat_id'])

            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(run_monitoring())
    except KeyboardInterrupt:
        pass
