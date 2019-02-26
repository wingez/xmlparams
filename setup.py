from setuptools import setup

setup(
    name='CICU parameters',
    author='Tekniksprånget VT-19',
    version='0.1',
    py_modules=['yourscript'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        cicuparams=program:cli
    ''',
)