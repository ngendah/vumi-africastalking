from setuptools import setup, find_packages

setup(
    name='vumi-africastalking',
    version=open('VERSION', 'r').read().strip(),
    license='BSD',
    description='AfricasTalking transport for Vumi and Junebug',
    long_description=open('README.rst', 'r').read(),
    author='Ngenda Henry',
    author_email='ngendahk@gmail.com',
    packages=find_packages(),
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