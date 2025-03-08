from setuptools import setup, find_packages

setup(
    name="auto-commit",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "g4f",
        "rich",
    ],
    entry_points={
        'console_scripts': [
            'auto-commit=auto_commit.cli:main_cli',
        ],
    },
    author="Alaamer",
    author_email="",
    description="An Intelligent Git Commit Message Generator",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Version Control :: Git",
    ],
    python_requires=">=3.6",
)
