from telegram.ext import Updater, CommandHandler
import requests
import psycopg2
import datetime
import matplotlib.pyplot as plt
import psql_credentials as psql
import tg_credentials as tg
import os

#command = 'CREATE TABLE rates (id BIGSERIAL NOT NULL PRIMARY KEY, {});'.format('\n'.join('"{}"'.format(str(key)) + ' NUMERIC(9,2) NOT NULL,' if key != list(rates.keys())[-1] else '"{}"'.format(str(key)) + ' NUMERIC(9,2) NOT NULL' for key in list(rates.keys())))
connection = psycopg2.connect(user=psql.user,
                              password=psql.password,
                              host=psql.host,
                              port=psql.port,
                              database=psql.database)
precision = 2

def get_lst():
    cursor = connection.cursor()
    command = '''SELECT * FROM rates
                ORDER BY id DESC
                LIMIT 1;'''
    cursor.execute(command)
    last_data = cursor.fetchone()
    if (datetime.datetime.now() - last_data[-1]).seconds / 60.0 < 10.0:
        command = "SELECT column_name FROM information_schema.columns WHERE table_name = 'rates';"
        cursor.execute(command)
        currencies = [i[0] for i in cursor.fetchall()[1:-1]]
        lst = ['{}: {}'.format(i, j) for i, j in zip(currencies, last_data[1:-1])]
    else:
        last_call = datetime.datetime.now()
        request = 'https://api.exchangerate.host/latest?base=USD&places={}'.format(precision)
        content = requests.get(request).json()
        rates = dict(content['rates'].items())
        lst = ['{}: {}'.format(i, j) for i, j in rates.items()]
        command = "INSERT INTO rates (date, {}) VALUES('{}', {});".format(' ,'.join(['"{}"'.format(key) for key in rates.keys()]), last_call, ' ,'.join([str(i) for i in rates.values()]))
        cursor.execute(command)
        connection.commit()

    cursor.close()
    return lst

def lst(update, context):
    update.message.reply_text('\n'.join(get_lst()))

def exchange(update, context):
    amount = context.args[0]
    from_curr = context.args[1]
    to_curr = context.args[3]
    request = 'https://api.exchangerate.host/convert?from={}&to={}&amount={}&places={}'.format(from_curr, to_curr, amount, precision)
    responce = requests.get(request).json()
    update.message.reply_text(responce['result'])

def get_history_data(from_curr, to_curr, period):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=period-1)
    request = 'https://api.exchangerate.host/timeseries?start_date={}&end_date={}&places={}&base={}&symbols={}'.format(start_date,
                                                                                                                       end_date,
                                                                                                                       precision,
                                                                                                                       from_curr,
                                                                                                                       to_curr)
    responce = requests.get(request).json()
    if not responce['success']:
        return {}
    return responce['rates']

def generate_graph_img(data, from_curr, to_curr, period):
    if not data:
        return
    dates = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in data.keys()]
    try:
        rates = [rate[to_curr] for rate in data.values()]
    except:
        return
    plt.subplots()[0].autofmt_xdate()
    plt.plot(dates, rates)
    plt.title('{}/{} exchange rate for {} days'.format(from_curr, to_curr, period))
    plt.xlabel('Date')
    plt.ylabel('Rate')

    plt.savefig('graph.png')

def history(update, context):
    from_curr, to_curr = context.args[0].split('/')
    period = int(context.args[2])
    data = get_history_data(from_curr, to_curr, period)
    generate_graph_img(data, from_curr, to_curr, period)
    if os.path.exists('graph.png'):
        update.message.reply_photo(open('graph.png', 'rb'))
        os.remove('graph.png')
    else:
        update.message.reply_text('No exchange rate data available for the selected currency')

def main():
    updater = Updater(tg.token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('lst', lst))
    dispatcher.add_handler(CommandHandler('exchange', exchange))
    dispatcher.add_handler(CommandHandler('history', history))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

