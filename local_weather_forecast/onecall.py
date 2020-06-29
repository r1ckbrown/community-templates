from urllib import request
from datetime import datetime, date
import sys
import json
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

###################
# 2020 thisispoki #
###################
# Did I get called by Telegraf, or am I testing?
if len(sys.argv) == 4:
    cityid = str(sys.argv[1])
    units = str(sys.argv[2])
    appid = str(sys.argv[3])
else:
    cityid = '5391959'
    units = 'metric'
    appid = ''

# This function sets the common tags for each line we'll be generating
# There's a case for lat and lon to be values rather than tags, but it's unclear as to the relative importance of
# InfluxDB v1.x GROUP BY or Flux geo functions. 
def getCoreFields(jsonContent, city):
    return ','.join(['weather',
                'city=' + city,
                'lat=' + str(jsonContent['lat']),
                'lon=' + str(jsonContent['lon']),
                'timezone=' + str(jsonContent['timezone']),
                'timezone_offset=' + str(jsonContent['timezone_offset']) + 'i'])

# Each line will have a set of common fields
def getRepeatedFields(jsonContent):
    return ','.join(['temp=' + str(jsonContent['temp']),
                'feels_like=' + str(jsonContent['feels_like']),
                'pressure=' + str(jsonContent['pressure']) + 'i',
                'humidity=' + str(jsonContent['humidity']) + 'i',
                'dew_point=' + str(jsonContent['dew_point']),
                'clouds=' + str(jsonContent['clouds']) + 'i',
                'wind_speed=' + str(jsonContent['wind_speed']),
                'wind_deg=' + str(jsonContent['wind_deg']) + 'i',
                'description="' + jsonContent['weather'][0]['description'] + '"'])

# Date mathematics, to determine the local HH:mm:ss given an epoch timestamp and a timezone offset
def getTimeFromDateTimeOffset(rawTime, offset):
    timeEpoch = rawTime + offset
    timeObject = datetime.fromtimestamp(timeEpoch)
    return str(timeObject.hour).zfill(2) + ':' + str(timeObject.minute).zfill(2) + ':' + str(timeObject.second).zfill(2)

################
# Start of doing things. Start with a call to get the lon, lat & city from the cityid
################
thisurl = 'https://api.openweathermap.org/data/2.5/weather?id=' + cityid + '&appid=' + appid
contents = request.urlopen(thisurl).read()
jsonContent = json.loads(contents)
lat = str(jsonContent['coord']['lat'])
lon = str(jsonContent['coord']['lon'])
city = str(jsonContent['name'])

################
# Now we've built all the URL parameters we'll need, let's make the actual call
################
contents = request.urlopen("https://api.openweathermap.org/data/2.5/onecall?lat=" + lat + "&lon=" + lon + "&exclude=minutely&units=" + units + "&appid=" + appid).read()
jsonContent = json.loads(contents)

# Start building the output. Note that city is a tag, and it might have special characters, so quote them
coreoutput = getCoreFields(jsonContent, city.replace(' ', '\ ').replace(',','\,'))

#current weather variables
timezone_offset = jsonContent['timezone_offset']
timestamp = jsonContent['current']['dt'] * 1000000000
sunrise = getTimeFromDateTimeOffset(jsonContent['current']['sunrise'], timezone_offset)
sunset = getTimeFromDateTimeOffset(jsonContent['current']['sunset'], timezone_offset)
today = date.fromtimestamp(jsonContent['current']['sunrise'] + timezone_offset)

currentLineProtocol = getRepeatedFields(jsonContent['current'])

# Construct the rest of the line protocol for the current weather
output = ','.join([coreoutput,
            'forecast=0h '
            'today="' + str(today) + '"',
            'sunrise="' + sunrise + '"',
            'sunset="' + sunset + '"',
            'uvi=' + str(jsonContent['current']['uvi']),
            currentLineProtocol + ' ' + str(timestamp)])

# Store the whole line into a list so it can be quickly extracted
outputlist = [output]

# Loop around all 48 hours of hourly forecasts, joining the fields with the core data we captured earlier
hourNumber=1
for hourly in jsonContent['hourly']:
    #hourly forecast
    output = ','.join([coreoutput,
            'forecast=' + str(hourNumber) + 'h ' + getRepeatedFields(hourly) + ' ' + str(hourly['dt'] * 1000000000)])
    outputlist.append(output)
    hourNumber += 1

# Loop around all 8 days of daily forecasts, joining the fields with the core data we captured earlier
dayNumber=0
for daily in jsonContent['daily']:
    #Daily forecast
    timestamp = daily['dt'] * 1000000000
    sunrise = getTimeFromDateTimeOffset(daily['sunrise'], timezone_offset)
    sunset = getTimeFromDateTimeOffset(daily['sunset'], timezone_offset)
    today = date.fromtimestamp(daily['sunrise'] + timezone_offset)

    # temp and feels_like are JSON objects, containing day, morn, eve, max, night, min, etc.
    #  for now, let's just use the 'day' temperatures
    daily['temp'] = daily['temp']['day']
    daily['feels_like'] = daily['feels_like']['day']
    output = ','.join([coreoutput,
            'today=' + str(today),
            'sunrise=' + sunrise,
            'sunset=' + sunset,
            'uvi=' + str(daily['uvi']),
            'forecast=' + str(dayNumber) + 'd ' + getRepeatedFields(daily) + ' ' + str(daily['dt'] * 1000000000)])
    outputlist.append(output)
    dayNumber += 1

# Quickly output all the stored lines
finalOutput = '\n'.join(outputlist)
print(finalOutput)