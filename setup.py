import setuptools
from distutils.core import setup

setuptools.setup(
    name='pysbr',
    version='0.1',
    author='Jean-Baptiste BESNARD',
    description='This is a python Second BRain implementation.',
    entry_points = {
        'console_scripts': ['sb=sbr.sbr:run'],
    },
    packages=["sbr"],
    install_requires=[
        'rich',
        'pyyaml'
    ],
    python_requires='>=3.5'
)
