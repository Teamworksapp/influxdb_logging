# sample ./setup.py file
from setuptools import setup

setup(
    name="influx_logging",
    description="Handlers for using InfluxDB as your logging backend.",
    url="https://github.com/teamworksapp/influx_logging",
    author="Jefferson Heard",
    author_email="jheard@teamworks.com",
    license = "MIT",
    packages = ['influx_logging','tests'],
    version = "0.1.3",

    # custom PyPI classifier for pytest plugins
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Logging"
    ],

    install_requires=["influxdb"],
    python_requires='>=3'
)
