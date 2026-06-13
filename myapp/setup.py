from setuptools import setup
setup(
    name='myapp',
    version='0.1',
    packages=['myapp'],
    entry_points={
        'console_scripts': ['myapp = myapp.hello:main']
    }
)
