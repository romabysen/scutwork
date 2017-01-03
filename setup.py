from setuptools import setup

setup(
    name='scutwork',
    version='1.0.0',
    license='New BSD',
    py_modules=['scutwork'],
    install_requires=[
        'click>=6.6',
        'crontab>=0.21.3',
        'pytimeparse>=1.1.5'
    ],
    entry_points='''
        [console_scripts]
        scutwork=scutwork:main
    ''',
)
