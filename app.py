
from flask import Flask, render_template, request, flash
import requests, os
import time
from flask_mail import Mail, Message
from dotenv import load_dotenv
from flask_caching import Cache
from collections import defaultdict
from datetime import datetime
import secrets
#print(secrets.token_hex(32))
#venv\Scripts\activate
load_dotenv()


app = Flask(__name__)

app.config['CACHE_TYPE'] = 'SimpleCache'  # or 'filesystem' for larger apps
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
cache = Cache(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Mail config
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv('EMAIL_USER'),
    MAIL_PASSWORD=os.getenv('EMAIL_PASS')
)
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')


mail = Mail(app)

API_KEY = os.getenv('WEATHER_API')


def format_time(timestamp, tz_offset=0):
    return datetime.fromtimestamp(timestamp + tz_offset).strftime('%H:%M')


@cache.memoize(300)
def get_weather_data(city, unit):
    print(f"Fetching new weather data for {city} in {unit} units...")
    forecast_data = None
    current_weather = None
    hourly_data = None
    city_name = None
    unit = 'metric'  # default
    unit_symbol = '°C'
    custom_alerts = []

    # Get current weather
    current_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units={unit}"
    current_response = requests.get(current_url)
    current_data = current_response.json()
    #print(current_data)

    if current_data.get("cod") != 200:
        flash("City not found!", "danger")
    else:
        city_name = current_data['name']
        current_weather = {
            'temp': int(current_data['main']['temp']),
            'feels_like': int(current_data['main']['feels_like']),
            'description': current_data['weather'][0]['description'],
            'humidity': current_data['main']['humidity'],
            'wind': int(current_data['wind']['speed']),
            'icon': current_data['weather'][0]['icon'],
            'rain': current_data.get('rain', {}).get('3h', 0),
            'pop': int(current_data.get('pop', 0.0) * 100),
            'sunrise': format_time(current_data['sys']['sunrise'], current_data['timezone']),
            'sunset': format_time(current_data['sys']['sunset'], current_data['timezone'])
        }
        # Custom alerts based on thresholds
        if current_weather['temp'] > 35:
            custom_alerts.append("🥵 Heat alert: Stay cool and hydrated!")

        if current_weather['temp'] < 0:
            custom_alerts.append("❄️ Freezing temperatures: Wear warm clothes!")

        if current_weather['wind'] > 40:
            custom_alerts.append("🌬️ Strong winds: Secure outdoor items.")

        if current_weather['rain'] > 10:
            custom_alerts.append("☔ Heavy rain expected: Carry an umbrella.")


        # Forecast
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units={unit}"
        response = requests.get(url)
        data = response.json()
        #print(data)
        hourly_data = []
        for entry in data['list'][:4]:  # next ~12 hours (4 entries)
            from datetime import datetime
            hourly_data.append({
                'time': datetime.strptime(entry['dt_txt'], "%Y-%m-%d %H:%M:%S").strftime('%H:%M'),
                'temp': int(entry['main']['temp']),
                'icon': entry['weather'][0]['icon'],
                'pop': int(entry.get('pop', 0.0) * 100),
                'rain': entry.get('rain', {}).get('3h', 0),
                'wind': int(entry['wind']['speed'])
            })
        
            
        if data.get("cod") == "200":
            from collections import defaultdict
            from datetime import datetime
            daily_data = defaultdict(list)
            for entry in data['list']:
                date = datetime.fromtimestamp(entry['dt']).strftime('%Y-%m-%d')
                daily_data[date].append(entry)

            forecast_data = []
            for date, entries in list(daily_data.items())[:6]:
                temps = [e['main']['temp'] for e in entries]
                temp_min = min(e['main']['temp_min'] for e in entries)
                temp_max = max(e['main']['temp_max'] for e in entries)
                humidity = sum(e['main']['humidity'] for e in entries) / len(entries)
                wind_speeds = [e['wind']['speed'] for e in entries]
                wind_min = min(wind_speeds)
                wind_max = max(wind_speeds)
                description = entries[0]['weather'][0]['description']
                icon = entries[0]['weather'][0]['icon']

                forecast_data.append({
                    'date': date,
                    'temp_avg': int(round(sum(temps)/len(temps), 1)),
                    'temp_min': int(round(temp_min, 1)),
                    'temp_max': int(round(temp_max, 1)),
                    'humidity': int(humidity),
                    'description': description,
                    'icon': icon,
                    'wind_min': int(round(wind_min, 1)),
                    'wind_max': int(round(wind_max, 1)),
                    'wind_avg': int(round(sum(wind_speeds) / len(wind_speeds), 1)) 
                })
                
    return current_weather, hourly_data, forecast_data, custom_alerts, city_name, data




@app.route('/', methods=['GET', 'POST'])
def index():
    forecast_data = None
    current_weather = None
    hourly_data = None
    city_name = None
    unit = 'metric'  # default
    unit_symbol = '°C'
    custom_alerts = []
    if request.method == 'POST':
        city = request.form.get('city')
        email = request.form.get('email')
        unit = request.form.get('unit', 'metric')
        unit_symbol = '°F' if unit == 'imperial' else '°C'

        current_weather, hourly_data, forecast_data, custom_alerts, city_name, data = get_weather_data(city, unit)
                 
        # Send email (optional)
        if email:
            msg = Message(f"Weather Forecast for {data['city']['name']}", recipients=[email])
            body_lines = [f"{day['date']}: {day['temp_avg']}°C, {day['description']}, Humidity: {day['humidity']}%"
                            for day in forecast_data]
            msg.body = "\n".join(body_lines)
            mail.send(msg)
            flash("Forecast emailed successfully!", "success")

    return render_template('index.html',
                           city=city_name,
                           current=current_weather,
                           hourly=hourly_data,
                           forecast=forecast_data,
                           unit=unit,
                           unit_symbol=unit_symbol,
                           custom_alerts=custom_alerts)


if __name__ == '__main__':
    app.run(debug=True)