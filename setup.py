from pathlib import Path
from setuptools import setup, find_packages
from re import findall, M

packages = ["ayla_iot_unofficial"]

# The directory containing this file
HERE = Path(__file__).parent.resolve()

# The text of the README file
README = (HERE / "README.md").read_text("utf-8")

# The text of the LICENSE file
LICENSE = (HERE / "LICENSE").read_text("utf-8")

# Pull the version from __init__.py so we don't need to maintain it in multiple places
init_txt = (HERE / "src" / packages[0] / "__init__.py").read_text("utf-8")
try:
    version = findall(r"^__version__ = ['\"]([^'\"]+)['\"]\r?$", init_txt, M)[0]
except IndexError:
    raise RuntimeError('Unable to determine version.')


setup(
    name="ayla_iot_unofficial",
    version=version,
    description="Python API for Ayla IoT products",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/rewardone/ayla-iot-unofficial",
    project_urls={
        "Bug Tracker": "https://github.com/rewardone/ayla-iot-unofficial/issues"
    },
    author="Reward One",
    author_email="rewardone@gmail.com",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    package_dir={'':"src"},
    packages=find_packages("src"),
    include_package_data=False
)