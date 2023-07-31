#!/usr/bin/env python3

from setuptools import setup, find_packages


setup(
    name="rfidclient",
    version="1.0.0",
    description="",
    url="https://github.com/decaturmakers/RPiRFIDWiegandReader",
    license="Copyright",
    author="Evan Goode",
    author_email="mail@evangoo.de",
    install_requires=[
        "gpiozero", "python-dotenv", "requests", "timeout-decorator",
        "prometheus-client"
    ],
    package_data={
        "": ["wiegand_rpi", "wiegand_rpi_arm64"],
    },
    include_package_data=True,
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "rfidclient=rfidclient.rfidclient:main",
            "rfid-prometheus=rfidclient.prometheus_client:main",
        ]
    },
)
