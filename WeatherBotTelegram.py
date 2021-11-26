from telebot import types
from datetime import *
import requests
import telebot
import psycopg2
import rollbar
from math import ceil
import os
from dotenv import load_dotenv

load_dotenv()

rollbar.init(os.getenv('ROLLBAR_ACCESS_TOKEN'))
token = os.getenv("2121108045:AAHDsyrirUdcyI74TLwvYnHiagQMJdq8vsg")


# database connection
def connect():
    conn = psycopg2.connect(database=os.getenv('postgres://sfaznsidrztonf:5acb7262d99f2fcd2d2533313003b9f9a6cb375b59cf855b53f2853cc01d9a6b@ec2-52-71-217-158.compute-1.amazonaws.com:5432/d5roea4vt57mh6'),
                            user=os.getenv('sfaznsidrztonf'),
                            password=os.getenv('5acb7262d99f2fcd2d2533313003b9f9a6cb375b59cf855b53f2853cc01d9a6b'),
                            host=os.getenv('ec2-52-71-217-158.compute-1.amazonaws.com'),
                            port=os.getenv('5432'))
    cursor = conn.cursor()
    return cursor, conn


# add new user data or updating state
def db_users(id, state):
    cursor, conn = connect()
    cursor.execute(f'SELECT user_id FROM users WHERE user_id = {id}')
    select = cursor.fetchone()
    if select is None:
        cursor.execute("INSERT INTO users (user_id, state, created_at, updated_at)"
                       f" VALUES ({id}, '{state}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    else:
        cursor.execute(f"UPDATE users SET state = '{state}', updated_at = CURRENT_TIMESTAMP WHERE user_id = {id}")
    conn.commit()
    cursor.close()
    conn.close()


def actions(query):
    cursor, conn = connect()
    cursor.execute(query)
    conn.commit()
    cursor.close()
    conn.close()


bot = telebot.TeleBot(token)

MAIN_STATE = "main"
CITY_STATE = 'city'
WEATHER_DATE_STATE = "weather_date_handler"

data = {'states': {}, MAIN_STATE: {}, CITY_STATE: {}, WEATHER_DATE_STATE: {}, 'forecast': {}, }

# dictionaries for translation into Russian
week_day = {'Mon': 'الأثنين',
            'Tue': 'الثلاثاء',
            'Wed': "الاربعاء",
            'Thu': "الخميس",
            'Fri': "الجمعة",
            'Sat': "السبت",
            'Sun': "الاحد"}

month_dict = {"January": "كانون الثاني",
              "February": "شباط",
              "March": "اذار",
              "April": "نيسان",
              "May": "ايار",
              "June": "حزيران",
              "July": "تموز",
              "August": "اب",
              "September": "ايلول",
              "October": "تشرين الاول",
              "November": "تشرين الثاني",
              "December": "كانون الاول"
              }

api_url = 'https://stepik.akentev.com/api/weather'


@bot.message_handler(func=lambda message: True)
def dispatcher(message):
    user_id = message.from_user.id
    state = data["states"].get(user_id, MAIN_STATE)
    db_users(id=user_id, state=state)

    if state == MAIN_STATE:
        main_handler(message)
    elif state == CITY_STATE:
        city_handler(message)
    elif state == WEATHER_DATE_STATE:
        weather_date(message)


# dialog start function
def main_handler(message):
    user_id = message.from_user.id

    if message.text.lower() == "/start" or message.text.lower() == 'погода':
        bot.send_message(user_id, "أدخل اسم المدينة لمعرفة الطقس")
        data["states"][user_id] = CITY_STATE

    elif '/reset' in message.text.lower():
        bot.send_message(message.from_user.id, 'اكتملت إعادة التشغيل ، أدخل اسم المدينة للتحقق من الطقس')
        data["states"][user_id] = CITY_STATE

    else:
        bot.send_message(user_id, "انا لا افهمك")


# function with entering the name of the city
def city_handler(message):
    user_id = message.from_user.id

    if '/reset' in message.text.lower():
        data["states"][user_id] = CITY_STATE
        bot.send_message(message.from_user.id, 'اكتملت إعادة التشغيل ، أدخل اسم المدينة للتحقق من الطقس')

    else:
        data[WEATHER_DATE_STATE][user_id] = message.text.lower()
        city = data[WEATHER_DATE_STATE][user_id]
        response = requests.get(api_url, params={'city': city, 'forecast': 0})
        data_ = response.json()

        # check for the wrong city name
        if 'error' in data_:
            bot.send_message(message.from_user.id, "أدخلت المدينة الخطأ ، اكتب اسم المدينة مرة أخرى")
            data["states"][user_id] = CITY_STATE

        else:
            def timestamp(delta=0):
                day = datetime.today() + timedelta(days=delta)
                return day

            # create buttons
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(*[types.KeyboardButton(button) for button in
                         ["Сегодня (" + week_day[timestamp().strftime("%a")] + ", " + timestamp().strftime("%d") + " " +
                          month_dict[timestamp().strftime("%B")] + ")",
                          "Завтра (" + week_day[timestamp(1).strftime("%a")] + ", " + timestamp(1).strftime(
                              "%d") + " " + month_dict[timestamp(1).strftime("%B")] + ")",
                          "Послезавтра (" + week_day[timestamp(2).strftime("%a")] + ", " + timestamp(2).strftime(
                              "%d") + " " +
                          month_dict[timestamp(2).strftime("%B")] + ")"]])
            bot.send_message(user_id, 'اليوم ، غدا ، بعد غد؟', reply_markup=markup)
            data["states"][user_id] = WEATHER_DATE_STATE


# function for entering the weather forecast day
def weather_date(message):
    user_id = message.from_user.id
    city = data[WEATHER_DATE_STATE][user_id]
    data['forecast'][user_id] = message.text.lower()
    data_forecast = data['forecast'][user_id]

    if "/reset" in message.text.lower():
        data["states"][user_id] = CITY_STATE
        bot.send_message(message.from_user.id, 'اكتملت إعادة التشغيل ، أدخل اسم المدينة للتحقق من الطقس')

    else:
        def forecast_day():
            if "сегодня" in data_forecast:
                forecast_data = 0
            elif "послезавтра" in data_forecast:
                forecast_data = 2
            elif "завтра" in data_forecast:
                forecast_data = 1
            else:
                forecast_data = 3
            return forecast_data

        if forecast_day() == 3:
            bot.send_message(message.from_user.id, 'تم تحديد تاريخ خاطئ ، أعد الإدخال')

        response = requests.get(api_url, params={'city': city, 'forecast': forecast_day()})
        data_ = response.json()
        smile = data_['description']

        # smile function
        def weather_smile():
            cloud, sun, rain, snow, cloud_2, cloud_sun = '☁', '☀', '🌧', '❄', "🌥", "⛅"
            if "пасмурно" in smile:
                send_smile = cloud
            elif smile == "солнечно" or smile == 'ясно':
                send_smile = sun
            elif smile == 'облачно с прояснениями':
                send_smile = cloud_sun
            elif 'дождь' in smile:
                send_smile = rain
            elif 'снег' in smile:
                send_smile = snow
            elif smile == 'переменная облачность' or smile == 'небольшая облачность':
                send_smile = cloud_2
            else:
                send_smile = ''

            return send_smile

        # depending on the selected day, a response from the bot is created
        if "сегодня" in message.text.lower():
            bot.send_message(message.from_user.id,
                             f"За окном {data_['description']}  {weather_smile()},"
                             f" температура: {ceil(data_['temp'])}°C")
            data["states"][user_id] = CITY_STATE

        elif "послезавтра" in message.text.lower():
            bot.send_message(message.from_user.id,
                             f"За окном будет {data_['description']}  {weather_smile()},"
                             f" температура: {ceil(data_['temp'])}" + "°C")
            data["states"][user_id] = CITY_STATE

        elif "завтра" in message.text.lower():
            bot.send_message(message.from_user.id,
                             f"За окном будет {data_['description']}  {weather_smile()},"
                             f" температура: {ceil(data_['temp'])}" + "°C")
            data["states"][user_id] = CITY_STATE

        actions(query="INSERT INTO actions (user_id, city, forecast_day, created_at) "
                      f"VALUES({user_id}, '{city}', '{data_forecast}', CURRENT_TIMESTAMP)")


bot.polling()
