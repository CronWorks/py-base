from email import Encoders
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate
from os.path import basename
from smtplib import SMTP_SSL


def addEmailArgments(parser):
    parser.add_argument('-f',
                        '--email-from',
                        help="Email address to send from",
                        )
    parser.add_argument('-p',
                        '--email-password',
                        help="Email server password",
                        )
    parser.add_argument('-t',
                        '--email-to',
                        help="Email address to send to",
                        )


class Emailer:

    def __init__(self, out, smtpHost):
        self.out = out
        self.smtpHost = smtpHost

    def sendMessage(self, sender, password, recipient, subject, body, attachmentFilenames=[]):
        if type(attachmentFilenames) != list:
            attachmentFilenames = [attachmentFilenames]

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        msg['Date'] = formatdate(localtime=True)

        msg.attach(MIMEText(body, 'html'))

        for filename in attachmentFilenames:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(filename, "rb").read())
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % basename(filename))
            msg.attach(part)

        self.out.put("connecting...")
        mailServer = SMTP_SSL(self.smtpHost, 465)
        mailServer.ehlo()
        self.out.put("logging in...")
        mailServer.login(sender, password)
        self.out.put("sending...")
        mailServer.sendmail(sender, recipient, msg.as_string())  # raise if email is not sent
        mailServer.quit()
        self.out.put("done.")


class Gmailer(Emailer):

    def __init__(self, out):
        self.out = out
        self.smtpHost = 'smtp.gmail.com'


class CronWorksEmailer(Emailer):

    def __init__(self, out):
        self.out = out
        self.smtpHost = 'secure.emailsrvr.com'
