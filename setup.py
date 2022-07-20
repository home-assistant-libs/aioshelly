"""Setup module for aioshelly."""
from pathlib import Path

from setuptools import setup

PROJECT_DIR = Path(__file__).parent.resolve()
README_FILE = PROJECT_DIR / "README.md"
VERSION = "2.0.1"


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
    packages=["aioshelly"],
    python_requires=">=3.9",
    package_data={"aioshelly": ["py.typed"]},
    zip_safe=True,
    platforms="any",
    install_requires=list(val.strip() for val in open("requirements.txt")),
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
