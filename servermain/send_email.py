import smtplib
import re
import random
import logging
import traceback


def sendemainandcodeoutput(tosend_email):
    random_numbers = []
    for n in range(6):
        random_numbers.append(str(random.randint(0, 9)))
    codenumber = ''.join(random_numbers)
    m = re.search(r'@(.+?)\.', tosend_email)
    textmail_str = str(m.group(1))
    try:
        match textmail_str:
            case 'gmail':
                smtpPort = 587
                smtpServer = 'smtp.gmail.com'
                loginUsername = 'your_gmail_username@gmail.com'  #replace with your actual username
                loginPassword = 'your_gmail_password' #replace with your actual password

            case 'mail':
                smtpPort = 587
                smtpServer = 'smtp.mail.ru'
                loginUsername = 'maks.sarkisyan.05@bk.ru'
                loginPassword = 'jQ4ZATPpexeEYPfGRnXB'

            case 'yandex':
                smtpPort = 587
                smtpServer = 'smtp.yandex.ru'
                loginUsername = 'jeived777@yandex.ru'
                loginPassword = 'yjkuexjnggusbvlu'

            case 'bk':
                smtpPort = 587
                smtpServer = 'smtp.mail.ru'
                loginUsername = 'maks.sarkisyan.05@bk.ru'
                loginPassword = 'jQ4ZATPpexeEYPfGRnXB'

            case 'internet':
                smtpPort = 587
                smtpServer = 'smtp.mail.ru'
                loginUsername = 'maks.sarkisyan.05@bk.ru'
                loginPassword = 'jQ4ZATPpexeEYPfGRnXB'

            case 'inbox':
                smtpPort = 587
                smtpServer = 'smtp.mail.ru'
                loginUsername = 'maks.sarkisyan.05@bk.ru'
                loginPassword = 'jQ4ZATPpexeEYPfGRnXB'

            case 'list':
                smtpPort = 587
                smtpServer = 'smtp.mail.ru'
                loginUsername = 'maks.sarkisyan.05@bk.ru'
                loginPassword = 'jQ4ZATPpexeEYPfGRnXB'
        mailserver = smtplib.SMTP(smtpServer,smtpPort)
        mailserver.ehlo()
        mailserver.starttls()
        mailserver.ehlo()
        mailserver.login(loginUsername, loginPassword)
        message = f'Ваш код подтверждения: {codenumber}'.encode('utf-8')
        mailserver.sendmail(loginUsername,tosend_email, message)
        mailserver.quit()
        return codenumber, None  # Return code and no error (None)
    except Exception as e:
      logging.log.error(f"An unexpected error occurred in sendemainandcodeoutput: {str(e)}")
      logging.log.error(traceback.format_exc())
      return None, str(e) # Return None as code and error message
