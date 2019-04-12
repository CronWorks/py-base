#!/usr/bin/python
from socket import getaddrinfo, AF_INET, SOL_TCP
from urllib import urlopen
import re
import socket

from py_base import Job, Emailer
from subprocess import check_output
from json import dumps
from py_base.Emailer import addEmailArgments

IP_CHECK_URL = 'https://ident.me'


def checkMytop():
    '''
    Run the 'mytop' script and send an email to me via 'Gmailer' script
    '''

    job = Job('Status Reporter')
    addEmailArgments(job.parser)
    job.start()

    with job.out.indent("Running 'mytop'..."):
        try:
            report = check_output('mytop')
            job.out.put(report)
            job.out.put("done.")
        except OSError as e:
            report = "'mytop' failed. Is it installed? OSError was: '%s'" % e.strerror
            job.out.error(report)

    emailConfig = job.getEmailConfigFromArgsAndConfigFile()

    if emailConfig['email_enabled']:
        recipients = [e.strip() for e in emailConfig['email_to'].split(',')]
        for recipient in recipients:
            with job.out.indent("Sending an email to %s..." % recipient):
                machineName = socket.gethostname()
                Emailer.Gmailer(job.out).sendMessage(emailConfig['email_from'],
                                                     emailConfig['email_password'],
                                                     recipient,
                                                     'Status report for %s' % machineName,
                                                     '<html><pre>%s</pre></html>' % report)


def checkIpAddresses():
    '''
    Checks that the IP address of a host matches that set on the DNS record(s)
    If any IP addresses differ, it will send an email using Gmailer
    '''
    job = Job('Ip Checker')
    addEmailArgments(job.parser)
    job.parser.add_argument('--hostname',
                            required=True,
                            help="DNS hostname to compare IP address against",
                            )

    job.start()

    job.out.put("Checking IP addresses for %s..." % job.arguments['hostname'])
    myIpAddress = urlopen(IP_CHECK_URL).read().strip()
    job.out.put("Got address info for this server: <%s>" % myIpAddress)

    try:
        dnsAddress = getaddrinfo(job.arguments['hostname'], 80, AF_INET, 0, SOL_TCP)[0][4][0]
    except:
        dnsAddress = 'ERROR'
    job.out.put("Got address info: <%s> for %s" % (dnsAddress, job.arguments['hostname']))

    if myIpAddress != dnsAddress:
        job.out.put("Found differing address.")
        emailConfig = job.getEmailConfigFromArgsAndConfigFile()
        if not emailConfig['email_enabled']:
            job.out.put('Skipping email because email_enabled == False: %s' % dumps(emailConfig))
        else:
            subject = 'my ip has changed'
            recipients = emailConfig['email_to']
            body = """IpChecker has found a difference between DNS and actual IP addresses for host %s:

            My IP address: %s
            DNS entry for %s: %s
            """ % (job.arguments['hostname'],
                   myIpAddress,
                   job.arguments['hostname'],
                   dnsAddress)
            if type(recipients) == str or type(recipients) == unicode:
                recipients = [recipients]
            for recipient in recipients:
                with job.out.indent("Sending an email to %s..." % recipient):
                    Emailer.Gmailer(job.out).sendMessage(emailConfig['email_from'],
                                                         emailConfig['email_password'],
                                                         recipient,
                                                         subject,
                                                         '<html><pre>%s</pre></html>' % body)
    else:
        job.out.put("Addresses look good. Bye!")

    job.finish()


if __name__ == "__main__":
    import sys
    sys.argv.append('--hostname=google.com')  # force it to send an email
    checkIpAddresses()
    print 'got to the end without throwing'
