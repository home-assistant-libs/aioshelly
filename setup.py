"""Setup module for aioshelly."""

from pathlib import Path

from setuptools import find_packages, setup

PROJECT_DIR = Path(__file__).parent.resolve()
README_FILE = PROJECT_DIR / "README.md"
VERSION = "12.3.1"

with open("requirements.txt", encoding="utf-8") as file:  # noqa: PTH123
    requirements = file.read().splitlines()

setup(
    name="aioshelly",
    version=VERSION,
    license="Apache License 2.0",
    url="https://github.com/home-assistant-libs/aioshelly",
    author="Paulus Schoutsen",
    author_email="paulus@home-assistant.io",
    description="Asynchronous library to control Shelly devices.",
    long_description=README_FILE.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests", "tools"]),
    python_requires=">=3.11",
    package_data={"aioshelly": ["py.typed"]},
    zip_safe=True,
    platforms="any",
    install_requires=requirements,
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
