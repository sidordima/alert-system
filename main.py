import time
import logging
from code.classes import Status, Compare
from code.alert import send_telegram_message
import yaml

logging.basicConfig(
    filename="service_check.log",  # файл лога
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    raise ValueError(f"Couldn't read config file:{e}")

tasks = config['tasks']
for task in tasks:
    task['condition'] = []
    for cond in task['condition_true']:
        class_mame = next(iter(cond))
        match class_mame:
            case "Status":
                task['condition'].append(Status(**cond['Status']))
            case "Compare":
                task['condition'].append(Compare(**cond['Compare']))
    del task['condition_true']

tg = config['telegram']


if __name__ == "__main__":
    # создаем таймеры для каждого сервиса
    next_check = {task["name"]: 0 for task in config["tasks"]}
    while True:
        now = time.time()
        for task in config["tasks"]:
            name = task["name"]
            if now >= next_check[name]:
                prev_result = all([x.succ_check for x in task['condition']] + [x.last_status for x in task['condition']])
                _check = [x.check() for x in task['condition']]
                new_succ_check = [x.succ_check for x in task['condition']]
                new_last_status = [x.last_status for x in task['condition']]
                new_result = all(new_succ_check + new_last_status)
                logging.info(f"Task[{name}]: can check {all(new_succ_check)}, last result: {all(new_last_status)}")
                if prev_result==False and new_result==True:
                    send_telegram_message(f"{name} Resolved!",tg['token'],tg['chat_id'])
                elif prev_result==True and new_result==False:
                    send_telegram_message(f"{name} Alert!",tg['token'],tg['chat_id'])
                else:
                    pass
                next_check[name] = now + task["check_interval"]
        time.sleep(2)