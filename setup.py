from setuptools import setup

long_description = open("README.md").read()

setup(
    name="aioshelly",
    version="1.0.11",
    license="Apache License 2.0",
    url="https://github.com/home-assistant-libs/aioshelly",
    author="Paulus Schoutsen",
    author_email="paulus@home-assistant.io",
    description="Asynchronous library to control Shelly devices.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["aioshelly"],
    package_data={"aioshelly": ["py.typed"]},
    zip_safe=True,
    platforms="any",
    install_requires=list(val.strip() for val in open("requirements.txt")),
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
