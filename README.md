# custom_components для добавления терморегулятора Equation WiFi в HA

Обмен данными происходит через API SST-Cloud.

######configuration.yaml:

```
climate:
  - platform: sst_cloud
	name: Equation
	username: YOUR_USERNAME
	password: YOUR_PASSWORD
	min_temp: 5
	max_temp: 45
	boost_temp: 40
	sleep_temp: 25
```

| Параметр               | Описание                                                     |
| ---------------------- | -------------------------------------------------------------|
| `name`          	     | Имя терморегулятора                                          |                                                                                           |
| `username`             | Логин от учетной записи SST Cloud                            |
| `password`             | Пароль от учетной записи SST Cloud                           |
| `min_temp`             | Минимальная температура для установки                        |
| `max_temp`             | Максимальная температура для установки                       |
| `boost_temp`           | (дополнительный параметр) Температура для турбо режима       |
| `sleep_temp`           | (дополнительный параметр) Температура для ночного режима		|

![alt tag](https://github.com/Toha4/HA-Custom-Components-EquationWiFi/blob/master/screenshots/climate.png?raw=true "Screenshot")
![alt tag](https://github.com/Toha4/HA-Custom-Components-EquationWiFi/blob/master/screenshots/details.png?raw=true "Screenshot")