# packages/langgraph-kirokuforms/setup.py
from setuptools import setup, find_packages

setup(
    name="langgraph-kirokuforms",
    version="0.1.0",
    description="KirokuForms integration for LangGraph",
    author="KirokuForms Team",
    author_email="info@kirokuforms.com",
    url="https://github.com/kirokuforms/langgraph-kirokuforms",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "langgraph>=0.0.15",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
)
