from setuptools import setup, find_packages
from os.path import dirname, join
from json import load

configFilename = join(dirname(__file__), 'setup.conf')
config = load(open(configFilename))

setup(name=config['package'],
      version=config['version'],
      description=config['description'],
      maintainer=config['maintainer'],
      maintainer_email=config['maintainer_email'],
      license='GPL3+',
      url='http://cron.works',
      packages=find_packages(),
      scripts=[
               # 'shell_scripts/convert-video.sh',
               ],
      entry_points={'console_scripts': [
                                        'py-base-installer=py_base.DebianInstaller:main',
                                        'send-email-if-ip-changed=py_base.StatusReporter:checkIpAddresses',
                                        'send-email-with-mytop-report=py_base.StatusReporter:checkMytop',
                                        ],
                    },
    zip_safe=False
)

