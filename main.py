import time
from datetime import datetime
import logging
from code.classes import Status, Compare, SSLcheck
from code.alert import send_tg_msg
import yaml

logging.basicConfig(
    filename="service_check.log",  # log file
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
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


if __name__ == "__main__":
    config = read_config("config.yml")
    tasks = load_tasks(config)
    tg = config['telegram']

    # create timers for each tasks
    next_check = {task["name"]: 0 for task in config["tasks"]}
    while True:
        now = time.time()
        for task in config["tasks"]:
            name = task["name"]
            if now >= next_check[name]:
                prev_result = all([x.succ_check for x in task['condition']]
                                  + [x.last_status for x in task['condition']])
                _check = [x.check() for x in task['condition']]
                new_succ_check = [x.succ_check for x in task['condition']]
                new_last_status = [x.last_status for x in task['condition']]
                new_result = all(new_succ_check + new_last_status)
                logging.info(f"Task[{name}]: can check {all(new_succ_check)}, "
                             f"last result: {all(new_last_status)}")
                if prev_result is False and new_result is True:
                    send_tg_msg(f"{datetime.now():%Y-%m-%d %H:%M:%S}"
                                f" ✅{name} Resolved!", tg['token'],
                                tg['chat_id'])
                elif prev_result is True and new_result is False:
                    send_tg_msg(f"{datetime.now():%Y-%m-%d %H:%M:%S}"
                                f"❗{name} Alert!", tg['token'], tg['chat_id'])
                else:
                    pass
                next_check[name] = now + task["check_interval"]
        time.sleep(2)
