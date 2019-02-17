import os
from setuptools import setup, find_packages


def read_file(filename):
    filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), filename)
    return open(filepath, 'r').read()


setup(
    name='vumi-africastalking',
    version=read_file('VERSION'),
    license='BSD',
    description='AfricasTalking transport for Vumi and Junebug',
    long_description=read_file('README.rst'),
    author='Ngenda Henry',
    author_email='ngendahk@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'vumi>=0.6.0',
        'mock'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
    ],
)