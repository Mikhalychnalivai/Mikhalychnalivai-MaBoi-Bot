from setuptools import setup, find_packages

setup(
    name="your-bot",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "aiogram==3.11.0",
        "aiohttp==3.9.5",
        "python-dotenv==1.0.1",
        "docx2pdf==0.8.3",
        "pdf2docx==0.5.7",
        "requests==2.31.0"
    ],
)
