import logging
import os
import sys
import time

import requests
import telegram
from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import ErrorApiAnswer, ErrorKeyApiAnswer


load_dotenv()


PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: int = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


TOKENS = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
}


def check_tokens(TOKENS: dict):
    """Проверка наличия всех токенов. Возвращает список пустых токенов."""
    logging.debug('Проверка наличия всех токенов.')
    none_tokens = []
    for token_name in TOKENS:
        if globals()[token_name] is None:
            none_tokens.append(token_name)
    return not none_tokens
    # return all(TOKENS.values())


def send_message(bot: telegram.Bot, message: int):
    """Отправка сообщения в чат."""
    try:
        logging.info(
            f'Начало отправки сообщения {message} в Telegram'
        )
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(
            f'Сообщениe {message} отправлено в Telegram.'
        )
    except telegram.error.TelegramError as error:
        logging.exception(
            f'Ошибка отправки сообщения {message} в Telegram: {error}'
        )


def get_api_answer(timestamp: int):
    """Запрос к API."""
    try:
        logging.info(
            f'Начало запроса к API с параметром {timestamp}'
        )
        response = requests.get(
            url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Ошибка запроса к API:{error}. '
            f'Параметры:{ENDPOINT} {HEADERS} {timestamp}'
        ) from error
    if response.status_code != HTTPStatus.OK:
        raise ErrorApiAnswer(
            f'Не получен ответ API. Код ответа: {response.status_code}'
        )
    response_json = response.json()
    for error_key in ['error', 'code']:
        if error_key in response_json:
            raise ErrorKeyApiAnswer(
                f'Отказ сервера. В ответе найден ключ:{error_key}. '
                f'Ошибка:{response_json[error_key]}. '
                f'Параметры:{ENDPOINT} {HEADERS} {timestamp}'
            )
    logging.debug('Ответ API получен.')
    return response_json


def check_response(response: dict):
    """Проверяем ответа API."""
    logging.debug('Проверки ответа API.')
    if not isinstance(response, dict):
        raise TypeError(
            'Ответ содержит не словарь, а {type(response)}.'
        )
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks.')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(
            f'homeworks является не списком, а {type(homeworks)}.'
        )
    logging.debug('Ответ API содержит список homeworks.')
    return homeworks


def parse_status(homework: list):
    """Получение информации о статусе работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name.')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status.')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неизвестный статус работы - {status}'
        )
    logging.debug('Получена информация о статусе работы.')
    homework_name = homework.get('homework_name')
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{HOMEWORK_VERDICTS[status]}'
    )


def main():
    """Работа бота."""
    if not check_tokens(TOKENS):
        logging.critical('Отсутствие необходимых токенов. Бот не сработает')
        sys.exit('Неполный список токенов в настройках. Необходимы '
                 'PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    logging.info('Бот начал свою работу.')
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Нет новых статусов.')
                continue
            message = parse_status(homeworks[0])
            if last_message != message:
                send_message(bot, message)
                logging.debug('Бот начал свою работу.')
                last_message = message
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            if last_message != message:
                try:
                    send_message(bot, message)
                    last_message = message
                except Exception as error:
                    logging.exception(
                        f'Ошибка отправки сообщения {message} в Telegram: '
                        f'{error}'
                    )
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler(filename=__file__ + '.log', mode='w'),
            logging.StreamHandler(stream=sys.stdout)
        ],
        format='%(asctime)s, %(levelname)s, %(funcName)s, '
               '%(lineno)s, %(message)s',
    )
    main()
