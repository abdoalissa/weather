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
token = os.getenv("TELEGRAM_TOKEN")


bot = telebot.TeleBot(token)

MAIN_STATE = "main"
CITY_STATE = 'city'
WEATHER_DATE_STATE = "weather_date_handler"

data = {'states': {}, MAIN_STATE: {}, CITY_STATE: {}, WEATHER_DATE_STATE: {}, 'forecast': {}, }

# dictionaries for translation into Russian
week_day = {'Mon': 'الاثنين',
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

    if state == MAIN_STATE:
        main_handler(message)
    elif state == CITY_STATE:
        city_handler(message)
    elif state == WEATHER_DATE_STATE:
        weather_date(message)


# dialog start function
def main_handler(message):
    user_id = message.from_user.id

    if message.text.lower() == "/start" or message.text.lower() == 'طقس':
        bot.send_message(user_id, "أدخل اسم المدينة لمعرفة الطقس")
        data["states"][user_id] = CITY_STATE

    elif '/reset' in message.text.lower():
        bot.send_message(message.from_user.id, 'اكتملت إعادة التشغيل ، أدخل اسم المدينة للتحقق من الطقس')
        data["states"][user_id] = CITY_STATE

    else:
        bot.send_message(user_id, "أنا لا أفهمك")


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
                         ["اليوم (" + week_day[timestamp().strftime("%a")] + ", " + timestamp().strftime("%d") + " " +
                          month_dict[timestamp().strftime("%B")] + ")",
                          "غدا (" + week_day[timestamp(1).strftime("%a")] + ", " + timestamp(1).strftime(
                              "%d") + " " + month_dict[timestamp(1).strftime("%B")] + ")",
                          "بعد غد (" + week_day[timestamp(2).strftime("%a")] + ", " + timestamp(2).strftime(
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
            if "اليوم" in data_forecast:
                forecast_data = 0
            elif "بعد غد" in data_forecast:
                forecast_data = 2
            elif "غدا" in data_forecast:
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
         
            new_d = ""
            if "пасмурно" in data_['description']:
                new_d = "غائم غالبًا"
            elif data_['description'] == "солнечно":
                new_d = "مشمس"
            elif data_['description'] == "ясно":
                new_d = "صافي"
            elif data_['description'] == 'облачно с прояснениями':
                new_d = "غائم"
            elif 'дождь' in data_['description']:
                new_d = "ماطر"
            elif 'снег' in data_['description']:
                new_d = "مثلج"
            elif data_['description'] == 'переменная облачность':
                new_d = "غائم جزئيا"
            elif data_['description'] == 'небольшая облачность':
                new_d = "غائم قليلا"


        

        # depending on the selected day, a response from the bot is created
        if "اليوم" in message.text.lower():
            bot.send_message(message.from_user.id,
                             f"الطقس سيكون : {new_d}  {weather_smile()},"
                             f" درجة الحرارة: {ceil(data_['temp'])}°C")
            data["states"][user_id] = CITY_STATE

        elif "بعد غد" in message.text.lower():
            bot.send_message(message.from_user.id,
                             f"الطقس سيكون :  {new_d}  {weather_smile()},"
                             f" درجة الحرارة: {ceil(data_['temp'])}" + "°C")
            data["states"][user_id] = CITY_STATE

        elif "غدا" in message.text.lower():
            bot.send_message(message.from_user.id,
                             f"الطقس سيكون :  {new_d}  {weather_smile()},"
                             f" درجة الحرارة: {ceil(data_['temp'])}" + "°C")
            data["states"][user_id] = CITY_STATE

        


bot.polling()
