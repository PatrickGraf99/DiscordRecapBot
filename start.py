from datetime import datetime
import os
import sys
import time

import argparse
import logging

from dotenv import load_dotenv
from bot import RecapBot, get_bot_intents, add_commands

logger = logging.getLogger('ServerRecapBot.bot')



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', choices=['dev', 'prod'], default=None, type=str)
    args = parser.parse_args()
    mode: str = args.mode
    auto_mode = False
    if mode is None:
        auto_mode = True
        mode = 'dev'

    init_logs(mode)

    if mode == 'dev':
        if auto_mode:
            logger.warning('No mode was specified, defaulting to development')
        logger.info('Starting bot in development mode')

    elif mode == 'prod':
        answer = input('Bot about to run in production, continue? (y/n) ')
        while answer != 'y' and answer != 'n':
            print('Please enter either "y" or "n"')
            answer = input('Bot about to run in production, continue? (y/n) ')
        if answer == 'n':
            logger.info('Exiting bot')
            exit(0)
        elif answer == 'y':
            logger.info('Starting bot in production mode')

    load_dotenv()

    intents = get_bot_intents()

    token = os.getenv('DEV_TOKEN') if mode == 'dev' else os.getenv('PROD_TOKEN')
    data_path = 'data-dev' if mode == 'dev' else 'data-prod'

    bot = RecapBot(command_prefix='wrap:' ,intents=intents, mode=mode, data_path=data_path)
    add_commands(bot)
    bot.run(token)





def init_logs(mode: str) -> None:
    if not os.path.exists('logs'):
        os.mkdir('logs')

    timestamp_str: str = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H-%M-%S")
    logfile_name: str = f'logs-dev-{timestamp_str}.log' if mode == 'dev' else f'logs-prod-{timestamp_str}.log'
    level = logging.DEBUG if mode == 'dev' else logging.INFO

    file_handler = logging.FileHandler(os.path.join('logs',logfile_name))
    file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
                                                   datefmt='%Y-%m-%d %H:%M:%S'))
    file_handler.setLevel(level)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
                                                  datefmt='%Y-%m-%d %H:%M:%S'))
    stdout_handler.setLevel(level)

    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)



if __name__ == '__main__':
    main()