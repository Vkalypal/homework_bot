import os
import sys
import time
import telegram
import requests
import logging
from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600  # Секунд
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    token_dict = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
                  'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
                  'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    empty_token = []
    for token, value in token_dict.items():
        if value is None:
            empty_token.append(token)
    if empty_token:
        logger.critical(f'Отсутствует обязательная переменная окружения:'
                        f'{empty_token}\nПрограмма принудительно остановлена.')
        raise ValueError(
            f'Отсутствует обязательная переменная окружения:'
            f'{empty_token}\nПрограмма принудительно остановлена.'
        )


def send_message(bot, message):
    """Отправляет сообщение в телеграмм."""
    try:
        logger.info('Отправка сообщения в телеграмм...')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.setLevel(logging.DEBUG)
        logger.debug('Сообщение успешно отправлено')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}

    try:
        from json.decoder import JSONDecodeError
    except ImportError:
        JSONDecodeError = ValueError

    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
    except Exception:
        logger.error(f'Сбой в работе программы: '
                     f'Эндпоинт {ENDPOINT} недоступен. '
                     f'Код ответа API: {homework_statuses.status_code}')
    if homework_statuses.status_code != 200:
        raise Exception('Эндпоинт недоступен')

    try:
        print(homework_statuses.json())
        return homework_statuses.json()
    except JSONDecodeError:
        logger.error('Ответ API сервиса не преобразован в формат JSON')
        raise Exception('Ответ API сервиса не преобразован в формат JSON')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Не верный тип данных. Ожидаемый тип данных словарь. '
                     f'Получен {type(response)}')
        raise TypeError('Не верный тип данных. Ожидаемый тип данных словарь. '
                        f'Получен {type(response)}')

    if 'homeworks' not in response or 'current_date' not in response:
        error = ('Отсутсвуют ожидаемые ключи в ответе API. '
                 'Необходимы ключи homeworks и current_date. '
                 f'Содержимое ответа: {response}')
        logger.error(error)
        raise KeyError(error)

    if not isinstance(response.get('homeworks'), list):
        logger.error('Не верный тип данных. Ожидаемый тип данных список. '
                     f'Получен {type(response.get("homeworks"))}')
        raise TypeError('Не верный тип данных. Ожидаемый тип данных список. '
                        f'Получен {type(response.get("homeworks"))}')

    if not response.get('homeworks'):
        return None

    return response.get('homeworks')[0]


def parse_status(homework):
    """Получаем статус домашней работы."""
    if not homework:
        return ('Домашняя работа не взята в работу')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if not homework_name:
        logger.error('Нет ключа homework.')
        raise KeyError('Нет ключа homework.')
    if status not in HOMEWORK_VERDICTS.keys():
        logger.error(f'Недокументированный статус домашней работы: {status}')
        raise KeyError(f'Недокументированный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]

    return (f'Изменился статус проверки работы "{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    # Переменная для хранения повторяющейся ошибки
    new_message_error = ''
    # Переменная для хранения повторяющегося статуса
    new_message_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if new_message_status != message:
                send_message(bot, message)
                new_message_status = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if new_message_error != message:
                bot.send_message(TELEGRAM_CHAT_ID, message)
                new_message_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
